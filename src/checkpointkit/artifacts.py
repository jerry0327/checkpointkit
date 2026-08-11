"""Artifact snapshot and integrity verification."""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from ._validation import (
    load_json_object,
    require_integer,
    require_list,
    require_safe_relative_path,
    require_string,
    require_timestamp,
    resolve_under_base,
)
from .errors import StateValidationError, UnsafePathError
from .store import atomic_write_json

MANIFEST_SCHEMA_VERSION = 1
_MANIFEST_KIND = "artifact manifest"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


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


def _portable_relative(path: Path, base: Path, *, label: str) -> str:
    try:
        relative = path.resolve().relative_to(base.resolve())
    except ValueError as exc:
        raise UnsafePathError(f"{label} is outside base directory: {path}") from exc
    value = relative.as_posix()
    return value if value else "."


def validate_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise StateValidationError(
            f"Unsupported artifact-manifest schema {payload.get('schema_version')!r}; "
            f"expected {MANIFEST_SCHEMA_VERSION}"
        )
    require_timestamp(payload.get("created_at"), field="created_at", kind=_MANIFEST_KIND)
    if payload.get("algorithm") != "sha256":
        raise StateValidationError("Unsupported artifact hash algorithm")

    require_safe_relative_path(
        payload.get("base_dir"),
        field="base_dir",
        kind=_MANIFEST_KIND,
        allow_dot=True,
        allow_parent=True,
    )

    records = require_list(payload.get("files"), field="files", kind=_MANIFEST_KIND)
    seen_paths: set[str] = set()
    for index, raw_record in enumerate(records):
        if not isinstance(raw_record, dict):
            raise StateValidationError(f"artifact manifest file record {index} must be an object")
        path = require_safe_relative_path(
            raw_record.get("path"),
            field=f"files[{index}].path",
            kind=_MANIFEST_KIND,
        ).as_posix()
        if path in seen_paths:
            raise StateValidationError(f"artifact manifest contains duplicate path: {path}")
        seen_paths.add(path)
        require_integer(
            raw_record.get("size"),
            field=f"files[{index}].size",
            kind=_MANIFEST_KIND,
            minimum=0,
        )
        digest = require_string(
            raw_record.get("sha256"),
            field=f"files[{index}].sha256",
            kind=_MANIFEST_KIND,
        )
        if not _SHA256_RE.fullmatch(digest):
            raise StateValidationError(
                "artifact manifest field "
                f"'files[{index}].sha256' must be 64 lowercase hex characters"
            )

    if "roots" in payload:
        roots = require_list(payload["roots"], field="roots", kind=_MANIFEST_KIND)
        seen_roots: set[str] = set()
        for index, root in enumerate(roots):
            normalized = require_safe_relative_path(
                root,
                field=f"roots[{index}]",
                kind=_MANIFEST_KIND,
                allow_dot=True,
            ).as_posix()
            if normalized in seen_roots:
                raise StateValidationError(
                    f"artifact manifest contains duplicate root: {normalized}"
                )
            seen_roots.add(normalized)
    return payload


def snapshot(
    paths: Iterable[str | os.PathLike[str]],
    manifest_path: str | os.PathLike[str],
    *,
    base_dir: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    base = Path(base_dir or Path.cwd()).resolve()
    if not base.is_dir():
        raise NotADirectoryError(base)
    manifest_path = Path(manifest_path).resolve()
    inputs = [
        (base / Path(path)).resolve() if not Path(path).is_absolute() else Path(path).resolve()
        for path in paths
    ]
    if not inputs:
        raise StateValidationError("At least one artifact path is required")

    roots = [_portable_relative(path, base, label="Artifact root") for path in inputs]
    files = []
    for path in _iter_files(inputs):
        if path == manifest_path:
            continue
        relative = _portable_relative(path, base, label="Artifact")
        stat = path.stat()
        files.append(
            {
                "path": relative,
                "size": stat.st_size,
                "sha256": _sha256(path),
            }
        )

    manifest_parent = manifest_path.parent
    try:
        relative_base = Path(os.path.relpath(base, manifest_parent)).as_posix()
    except ValueError as exc:
        raise UnsafePathError(
            "Manifest and base directory must be on the same filesystem drive"
        ) from exc
    payload: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "algorithm": "sha256",
        "base_dir": relative_base,
        "roots": list(dict.fromkeys(roots)),
        "files": sorted(files, key=lambda item: item["path"]),
    }
    validate_manifest(payload)
    atomic_write_json(manifest_path, payload)
    return payload


def _manifest_base(manifest_path: Path, payload: dict[str, Any]) -> Path:
    relative = PurePosixPath(payload["base_dir"])
    return manifest_path.parent.joinpath(*relative.parts).resolve()


def _actual_files_for_roots(
    base: Path,
    roots: list[str],
    *,
    manifest_path: Path,
) -> set[str]:
    actual: set[str] = set()
    for raw_root in roots:
        relative = PurePosixPath(raw_root)
        root = (
            base
            if raw_root == "."
            else resolve_under_base(
                base,
                relative,
                label=f"artifact root {raw_root!r}",
            )
        )
        for path in _iter_files([root]):
            if path == manifest_path:
                continue
            actual.add(_portable_relative(path, base, label="Artifact"))
    return actual


def verify(
    manifest_path: str | os.PathLike[str],
    *,
    exact: bool = False,
) -> list[str]:
    manifest_path = Path(manifest_path).resolve()
    payload = load_json_object(manifest_path, kind=_MANIFEST_KIND)
    validate_manifest(payload)

    base = _manifest_base(manifest_path, payload)
    problems: list[str] = []
    expected_paths: set[str] = set()
    for record in payload["files"]:
        relative = PurePosixPath(record["path"])
        path = resolve_under_base(base, relative, label=f"artifact {record['path']!r}")
        expected_paths.add(record["path"])
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

    if exact:
        if "roots" not in payload:
            raise StateValidationError(
                "Exact verification requires a manifest created by CheckpointKit 0.1.0a1 or later"
            )
        actual_paths = _actual_files_for_roots(
            base,
            payload["roots"],
            manifest_path=manifest_path,
        )
        for unexpected in sorted(actual_paths - expected_paths):
            problems.append(f"unexpected: {unexpected}")

    return problems
