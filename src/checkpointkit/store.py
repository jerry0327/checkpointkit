"""Durable local checkpoint state."""

from __future__ import annotations

import copy
import json
import os
import tempfile
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

from ._validation import (
    load_json_object,
    require_integer,
    require_list,
    require_mapping,
    require_string,
    require_timestamp,
)
from .errors import StateConflictError, StateValidationError
from .locking import FileLock, lock_path_for

SCHEMA_VERSION = 1
_CHECKPOINT_KIND = "checkpoint"
_T = TypeVar("_T")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fsync_directory(path: Path) -> None:
    """Best-effort directory fsync after replacement on POSIX filesystems."""
    if os.name == "nt":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        directory_fd = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(directory_fd)
    except OSError:
        # Some filesystems do not support directory fsync. The file replacement
        # is still atomic, but crash durability depends on the filesystem.
        pass
    finally:
        os.close(directory_fd)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Atomically replace *path* with a UTF-8 JSON document.

    The new document is written and fsynced in the destination directory before
    ``os.replace``. A failed write leaves the previous checkpoint untouched and
    removes the temporary file.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            try:
                json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            except (TypeError, ValueError) as exc:
                raise StateValidationError(f"State is not JSON serializable: {path}") from exc
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        _fsync_directory(path.parent)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def _generation(payload: dict[str, Any]) -> int:
    return require_integer(
        payload.get("generation", 0),
        field="generation",
        kind=_CHECKPOINT_KIND,
        minimum=0,
    )


def validate_checkpoint(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and return an item checkpoint document.

    Schema-1 documents created before generation tracking are accepted and have
    a logical generation of zero. Validation does not rewrite the source file.
    """
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise StateValidationError(
            f"Unsupported checkpoint schema {payload.get('schema_version')!r}; "
            f"expected {SCHEMA_VERSION}"
        )

    if "generation" in payload:
        _generation(payload)
    require_timestamp(payload.get("created_at"), field="created_at", kind=_CHECKPOINT_KIND)
    require_timestamp(payload.get("updated_at"), field="updated_at", kind=_CHECKPOINT_KIND)

    completed = require_list(payload.get("completed"), field="completed", kind=_CHECKPOINT_KIND)
    normalized: list[str] = []
    for index, key in enumerate(completed):
        normalized.append(
            require_string(key, field=f"completed[{index}]", kind=_CHECKPOINT_KIND)
        )
    if len(normalized) != len(set(normalized)):
        raise StateValidationError("checkpoint field 'completed' cannot contain duplicates")

    require_mapping(payload.get("metadata"), field="metadata", kind=_CHECKPOINT_KIND)
    item_metadata = require_mapping(
        payload.get("item_metadata"),
        field="item_metadata",
        kind=_CHECKPOINT_KIND,
    )
    completed_set = set(normalized)
    for key, value in item_metadata.items():
        require_string(key, field="item_metadata key", kind=_CHECKPOINT_KIND)
        require_mapping(value, field=f"item_metadata[{key!r}]", kind=_CHECKPOINT_KIND)
        if key not in completed_set:
            raise StateValidationError(
                f"checkpoint item_metadata key {key!r} is not marked complete"
            )
    return payload


def _normalize_checkpoint(payload: dict[str, Any]) -> dict[str, Any]:
    validate_checkpoint(payload)
    if "generation" in payload:
        return payload
    normalized = dict(payload)
    normalized["generation"] = 0
    return normalized


class CheckpointStore:
    """A JSON-backed store for item-level completion state.

    Cooperating local writers serialize read-modify-write transactions with an
    operating-system advisory lock. Every durable write also checks a monotonic
    generation so stale in-memory snapshots fail with ``StateConflictError``
    instead of silently replacing newer progress.
    """

    def __init__(
        self,
        path: str | os.PathLike[str],
        *,
        lock_timeout: float = 10.0,
    ) -> None:
        self.path = Path(path)
        self.lock_timeout = float(lock_timeout)

    @property
    def lock_path(self) -> Path:
        """Return the sidecar path used to coordinate cooperating writers."""
        return lock_path_for(self.path)

    def _empty(self) -> dict[str, Any]:
        now = _now()
        return {
            "schema_version": SCHEMA_VERSION,
            "generation": 0,
            "created_at": now,
            "updated_at": now,
            "completed": [],
            "metadata": {},
            "item_metadata": {},
        }

    def _load_unlocked(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        payload = load_json_object(self.path, kind=_CHECKPOINT_KIND)
        return _normalize_checkpoint(payload)

    def load(self) -> dict[str, Any]:
        """Return validated state, normalizing legacy missing generation to zero."""
        return self._load_unlocked()

    def _write_next_unlocked(
        self,
        payload: dict[str, Any],
        *,
        expected_generation: int,
    ) -> dict[str, Any]:
        durable = self._load_unlocked()
        actual_generation = durable["generation"]
        if actual_generation != expected_generation:
            raise StateConflictError(
                f"State generation conflict for {self.path}: "
                f"expected {expected_generation}, found {actual_generation}"
            )

        candidate = copy.deepcopy(payload)
        candidate["schema_version"] = SCHEMA_VERSION
        candidate["generation"] = expected_generation + 1
        candidate["updated_at"] = _now()
        validate_checkpoint(candidate)
        atomic_write_json(self.path, candidate)
        return candidate

    def save(
        self,
        payload: dict[str, Any],
        *,
        expected_generation: int | None = None,
    ) -> dict[str, Any]:
        """Conditionally save *payload* and return the new durable state.

        By default the generation present in *payload* is used as the expected
        generation. Supplying ``expected_generation`` explicitly is useful when
        callers keep the token separately. A stale token raises
        ``StateConflictError`` without changing the durable document.
        """
        candidate = _normalize_checkpoint(copy.deepcopy(payload))
        expected = candidate["generation"] if expected_generation is None else require_integer(
            expected_generation,
            field="expected_generation",
            kind=_CHECKPOINT_KIND,
            minimum=0,
        )
        with FileLock(self.lock_path, timeout=self.lock_timeout):
            return self._write_next_unlocked(candidate, expected_generation=expected)

    def _mutate(self, operation: Callable[[dict[str, Any]], tuple[bool, _T]]) -> _T:
        with FileLock(self.lock_path, timeout=self.lock_timeout):
            payload = self._load_unlocked()
            changed, result = operation(payload)
            if changed:
                self._write_next_unlocked(
                    payload,
                    expected_generation=payload["generation"],
                )
            return result

    @staticmethod
    def _normalize_key(key: str) -> str:
        return require_string(str(key), field="completion key", kind=_CHECKPOINT_KIND)

    def is_complete(self, key: str) -> bool:
        normalized = self._normalize_key(key)
        return normalized in set(self.load()["completed"])

    def mark_complete(self, key: str, metadata: dict[str, Any] | None = None) -> None:
        normalized = self._normalize_key(key)
        if metadata is not None and not isinstance(metadata, dict):
            raise StateValidationError("item metadata must be a JSON object")

        def operation(payload: dict[str, Any]) -> tuple[bool, None]:
            changed = False
            if normalized not in payload["completed"]:
                payload["completed"].append(normalized)
                changed = True
            if metadata is not None:
                item_metadata = dict(metadata)
                if payload["item_metadata"].get(normalized) != item_metadata:
                    payload["item_metadata"][normalized] = item_metadata
                    changed = True
            return changed, None

        self._mutate(operation)

    def mark_incomplete(self, key: str) -> bool:
        """Remove a completion marker and associated item metadata.

        Returns ``True`` when an existing completion marker was removed.
        """
        normalized = self._normalize_key(key)

        def operation(payload: dict[str, Any]) -> tuple[bool, bool]:
            if normalized not in payload["completed"]:
                return False, False
            payload["completed"].remove(normalized)
            payload["item_metadata"].pop(normalized, None)
            return True, True

        return self._mutate(operation)

    def set_metadata(self, **values: Any) -> None:
        def operation(payload: dict[str, Any]) -> tuple[bool, None]:
            changed = any(
                key not in payload["metadata"] or payload["metadata"][key] != value
                for key, value in values.items()
            )
            if changed:
                payload["metadata"].update(values)
            return changed, None

        self._mutate(operation)

    def completed_count(self) -> int:
        return len(self.load()["completed"])

    def completed_keys(self) -> tuple[str, ...]:
        return tuple(self.load()["completed"])

    def pending_keys(self, keys: Iterable[str]) -> tuple[str, ...]:
        """Return unique input keys that are not marked complete, preserving order."""
        completed = set(self.load()["completed"])
        pending: list[str] = []
        seen: set[str] = set()
        for key in keys:
            normalized = self._normalize_key(key)
            if normalized not in completed and normalized not in seen:
                pending.append(normalized)
                seen.add(normalized)
        return tuple(pending)
