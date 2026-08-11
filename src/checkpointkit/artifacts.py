"""Artifact snapshot and integrity verification."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from .store import atomic_write_json

MANIFEST_SCHEMA_VERSION = 1


def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_files(paths: Iterable[Path]) -> Iterable[Path]:
    seen: set[Path] = set()
    for path in paths:
        if path.is_file():
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield resolved
        elif path.is_dir():
            for child in sorted(p for p in path.rglob("*") if p.is_file()):
                resolved = child.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    yield resolved
        else:
            raise FileNotFoundError(path)


def snapshot(
    paths: Iterable[str | os.PathLike[str]],
    manifest_path: str | os.PathLike[str],
    *,
    base_dir: str | os.PathLike[str] | None = None,
) -> dict:
    base = Path(base_dir or Path.cwd()).resolve()
    manifest_path = Path(manifest_path).resolve()
    inputs = [
        (base / Path(p)).resolve() if not Path(p).is_absolute() else Path(p).resolve()
        for p in paths
    ]

    files = []
    for path in _iter_files(inputs):
        if path == manifest_path:
            continue
        try:
            relative = path.relative_to(base)
        except ValueError as exc:
            raise ValueError(f"Artifact is outside base directory: {path}") from exc
        stat = path.stat()
        files.append(
            {
                "path": relative.as_posix(),
                "size": stat.st_size,
                "sha256": _sha256(path),
            }
        )

    manifest_parent = manifest_path.parent
    relative_base = os.path.relpath(base, manifest_parent)
    payload = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "algorithm": "sha256",
        "base_dir": relative_base,
        "files": sorted(files, key=lambda item: item["path"]),
    }
    atomic_write_json(manifest_path, payload)
    return payload


def verify(manifest_path: str | os.PathLike[str]) -> list[str]:
    manifest_path = Path(manifest_path).resolve()
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid artifact manifest JSON: {manifest_path}") from exc
    if payload.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError("Unsupported artifact-manifest schema")
    if payload.get("algorithm") != "sha256":
        raise ValueError("Unsupported artifact hash algorithm")

    base = (manifest_path.parent / payload.get("base_dir", ".")).resolve()
    problems: list[str] = []
    for record in payload.get("files", []):
        path = base / record["path"]
        if not path.is_file():
            problems.append(f"missing: {record['path']}")
            continue
        size = path.stat().st_size
        if size != record["size"]:
            problems.append(
                f"size mismatch: {record['path']} (expected {record['size']}, got {size})"
            )
            continue
        digest = _sha256(path)
        if digest != record["sha256"]:
            problems.append(f"hash mismatch: {record['path']}")
    return problems
