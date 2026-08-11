"""Durable local checkpoint state."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Atomically replace *path* with a UTF-8 JSON document."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


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
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid checkpoint JSON: {self.path}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"Checkpoint root must be an object: {self.path}")
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported checkpoint schema {payload.get('schema_version')!r}; "
                f"expected {SCHEMA_VERSION}"
            )
        if not isinstance(payload.get("completed"), list):
            raise ValueError("Checkpoint field 'completed' must be a list")
        return payload

    def save(self, payload: dict[str, Any]) -> None:
        payload = dict(payload)
        payload["schema_version"] = SCHEMA_VERSION
        payload["updated_at"] = _now()
        atomic_write_json(self.path, payload)

    def is_complete(self, key: str) -> bool:
        key = str(key)
        return key in set(self.load()["completed"])

    def mark_complete(self, key: str, metadata: dict[str, Any] | None = None) -> None:
        key = str(key)
        payload = self.load()
        if key not in payload["completed"]:
            payload["completed"].append(key)
        if metadata is not None:
            item_metadata = payload.setdefault("item_metadata", {})
            item_metadata[key] = metadata
        self.save(payload)

    def set_metadata(self, **values: Any) -> None:
        payload = self.load()
        payload.setdefault("metadata", {}).update(values)
        self.save(payload)

    def completed_count(self) -> int:
        return len(self.load()["completed"])

    def completed_keys(self) -> tuple[str, ...]:
        return tuple(self.load()["completed"])
