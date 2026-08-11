from pathlib import PurePosixPath

import pytest

from checkpointkit import StateValidationError, UnsafePathError
from checkpointkit._validation import (
    load_json_object,
    require_integer,
    require_list,
    require_mapping,
    require_safe_relative_path,
    require_string,
    require_timestamp,
    resolve_under_base,
)


def test_json_loader_rejects_invalid_utf8_and_non_object(tmp_path):
    invalid_utf8 = tmp_path / "invalid.json"
    invalid_utf8.write_bytes(b"\xff")
    with pytest.raises(StateValidationError, match="not valid UTF-8"):
        load_json_object(invalid_utf8, kind="test state")

    non_object = tmp_path / "list.json"
    non_object.write_text("[]", encoding="utf-8")
    with pytest.raises(StateValidationError, match="root must be a JSON object"):
        load_json_object(non_object, kind="test state")


def test_scalar_validators_reject_wrong_types_and_values():
    with pytest.raises(StateValidationError, match="must be an object"):
        require_mapping([], field="value", kind="test")
    with pytest.raises(StateValidationError, match="must be a list"):
        require_list({}, field="value", kind="test")
    with pytest.raises(StateValidationError, match="must be a string"):
        require_string(1, field="value", kind="test")
    with pytest.raises(StateValidationError, match="cannot be empty"):
        require_string("", field="value", kind="test")
    with pytest.raises(StateValidationError, match="cannot contain NUL"):
        require_string("bad\x00value", field="value", kind="test")
    with pytest.raises(StateValidationError, match="must be an integer"):
        require_integer(True, field="value", kind="test")
    with pytest.raises(StateValidationError, match="greater than or equal"):
        require_integer(-1, field="value", kind="test", minimum=0)


def test_timestamp_validator_accepts_z_and_rejects_invalid_or_naive_values():
    assert require_timestamp(
        "2026-08-11T00:00:00Z",
        field="time",
        kind="test",
    ).endswith("Z")
    with pytest.raises(StateValidationError, match="ISO 8601"):
        require_timestamp("not-a-time", field="time", kind="test")
    with pytest.raises(StateValidationError, match="include a timezone"):
        require_timestamp("2026-08-11T00:00:00", field="time", kind="test")


def test_relative_path_validator_dot_parent_and_portability_rules():
    assert require_safe_relative_path(
        ".", field="path", kind="test", allow_dot=True
    ) == PurePosixPath(".")
    with pytest.raises(UnsafePathError, match="cannot be '.'"):
        require_safe_relative_path(".", field="path", kind="test")
    with pytest.raises(UnsafePathError, match="cannot contain '..'"):
        require_safe_relative_path("a/../b", field="path", kind="test")
    assert require_safe_relative_path(
        "../base", field="path", kind="test", allow_parent=True
    ) == PurePosixPath("../base")
    with pytest.raises(UnsafePathError, match="must use '/' separators"):
        require_safe_relative_path(r"a\b", field="path", kind="test")
    with pytest.raises(UnsafePathError, match="drive prefix"):
        require_safe_relative_path("C:/file", field="path", kind="test")
    with pytest.raises(UnsafePathError, match="must be relative"):
        require_safe_relative_path("/file", field="path", kind="test")


def test_resolve_under_base_rejects_symlink_escape(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    base = tmp_path / "base"
    base.mkdir()
    link = base / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is not available")

    with pytest.raises(UnsafePathError, match="escapes"):
        resolve_under_base(base, PurePosixPath("link/secret.txt"), label="artifact")
