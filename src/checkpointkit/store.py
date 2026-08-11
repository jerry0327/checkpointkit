"""Durable local checkpoint state."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._validation import (
    load_json_object,
    require_list,
    require_mapping,
    require_string,
    require_timestamp,
)
from .errors import StateValidationError

SCHEMA_VERSION = 1
_CHECKPOINT_KIND = "checkpoint"


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


def validate_checkpoint(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and return an item checkpoint document."""
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise StateValidationError(
            f"Unsupported checkpoint schema {payload.get('schema_version')!r}; "
            f"expected {SCHEMA_VERSION}"
        )

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


class CheckpointStore:
    """A small JSON-backed store for item-level completion state.

    The local backend is intentionally single-writer. Atomic replacement protects
    against torn writes, but it does not serialize concurrent processes.
    """

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)

    def _empty(self) -> dict[str, Any]:
        now = _now()
        return {
            "schema_version": SCHEMA_VERSION,
            "created_at": now,
            "updated_at": now,
            "completed": [],
            "metadata": {},
            "item_metadata": {},
        }

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        payload = load_json_object(self.path, kind=_CHECKPOINT_KIND)
        return validate_checkpoint(payload)

    def save(self, payload: dict[str, Any]) -> None:
        payload = dict(payload)
        payload["schema_version"] = SCHEMA_VERSION
        payload["updated_at"] = _now()
        validate_checkpoint(payload)
        atomic_write_json(self.path, payload)

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

        payload = self.load()
        if normalized not in payload["completed"]:
            payload["completed"].append(normalized)
        if metadata is not None:
            payload["item_metadata"][normalized] = dict(metadata)
        self.save(payload)

    def mark_incomplete(self, key: str) -> bool:
        """Remove a completion marker and associated item metadata.

        Returns ``True`` when an existing completion marker was removed.
        """
        normalized = self._normalize_key(key)
        payload = self.load()
        if normalized not in payload["completed"]:
            return False
        payload["completed"].remove(normalized)
        payload["item_metadata"].pop(normalized, None)
        self.save(payload)
        return True

    def set_metadata(self, **values: Any) -> None:
        payload = self.load()
        payload["metadata"].update(values)
        self.save(payload)

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
