"""Validation helpers for durable JSON formats."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from .errors import StateValidationError, UnsafePathError


def load_json_object(path: Path, *, kind: str) -> dict[str, Any]:
    """Load *path* as a UTF-8 JSON object with stable error messages."""
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise StateValidationError(f"{kind} is not valid UTF-8: {path}") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StateValidationError(
            f"Invalid {kind} JSON at line {exc.lineno}, column {exc.colno}: {path}"
        ) from exc

    if not isinstance(payload, dict):
        raise StateValidationError(f"{kind} root must be a JSON object: {path}")
    return payload


def require_mapping(value: Any, *, field: str, kind: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StateValidationError(f"{kind} field {field!r} must be an object")
    return value


def require_list(value: Any, *, field: str, kind: str) -> list[Any]:
    if not isinstance(value, list):
        raise StateValidationError(f"{kind} field {field!r} must be a list")
    return value


def require_string(
    value: Any,
    *,
    field: str,
    kind: str,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str):
        raise StateValidationError(f"{kind} field {field!r} must be a string")
    if not allow_empty and not value:
        raise StateValidationError(f"{kind} field {field!r} cannot be empty")
    if "\x00" in value:
        raise StateValidationError(f"{kind} field {field!r} cannot contain NUL")
    return value


def require_integer(
    value: Any,
    *,
    field: str,
    kind: str,
    minimum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise StateValidationError(f"{kind} field {field!r} must be an integer")
    if minimum is not None and value < minimum:
        raise StateValidationError(
            f"{kind} field {field!r} must be greater than or equal to {minimum}"
        )
    return value


def require_timestamp(value: Any, *, field: str, kind: str) -> str:
    text = require_string(value, field=field, kind=kind)
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise StateValidationError(
            f"{kind} field {field!r} must be an ISO 8601 timestamp"
        ) from exc
    if parsed.tzinfo is None:
        raise StateValidationError(f"{kind} field {field!r} must include a timezone")
    return text


def require_safe_relative_path(
    value: Any,
    *,
    field: str,
    kind: str,
    allow_dot: bool = False,
    allow_parent: bool = False,
) -> PurePosixPath:
    """Validate a portable POSIX-style relative path stored in JSON."""
    text = require_string(value, field=field, kind=kind)
    if "\\" in text:
        raise UnsafePathError(f"{kind} field {field!r} must use '/' separators")
    if PureWindowsPath(text).drive:
        raise UnsafePathError(f"{kind} field {field!r} cannot contain a drive prefix")

    path = PurePosixPath(text)
    if path.is_absolute():
        raise UnsafePathError(f"{kind} field {field!r} must be relative")
    if text == ".":
        if allow_dot:
            return path
        raise UnsafePathError(f"{kind} field {field!r} cannot be '.'")
    if not path.parts:
        raise UnsafePathError(f"{kind} field {field!r} cannot be empty")
    if not allow_parent and ".." in path.parts:
        raise UnsafePathError(f"{kind} field {field!r} cannot contain '..'")
    return path


def resolve_under_base(base: Path, relative: PurePosixPath, *, label: str) -> Path:
    """Resolve *relative* under *base* and reject symlink/path escapes."""
    base = base.resolve()
    candidate = base.joinpath(*relative.parts).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise UnsafePathError(f"{label} escapes the declared base directory") from exc
    return candidate
