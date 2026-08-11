import json

import pytest

from checkpointkit import StateValidationError, UnsafePathError
from checkpointkit.artifacts import snapshot, verify


def _make_snapshot(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    (output / "a.txt").write_text("alpha", encoding="utf-8")
    (output / "b.txt").write_text("beta", encoding="utf-8")
    manifest = tmp_path / "artifacts.json"
    payload = snapshot(["output"], manifest, base_dir=tmp_path)
    return output, manifest, payload


def test_snapshot_and_verify(tmp_path):
    output, manifest, payload = _make_snapshot(tmp_path)

    assert [item["path"] for item in payload["files"]] == ["output/a.txt", "output/b.txt"]
    assert payload["roots"] == ["output"]
    assert verify(manifest) == []
    assert verify(manifest, exact=True) == []

    (output / "a.txt").write_text("changed", encoding="utf-8")
    problems = verify(manifest)
    assert len(problems) == 1
    assert "mismatch" in problems[0]


def test_verify_reports_missing_size_hash_and_unexpected_files(tmp_path):
    output, manifest, payload = _make_snapshot(tmp_path)

    (output / "a.txt").unlink()
    (output / "b.txt").write_text("BETA", encoding="utf-8")  # same length, different hash
    (output / "extra.txt").write_text("extra", encoding="utf-8")

    problems = verify(manifest, exact=True)
    assert "missing: output/a.txt" in problems
    assert "hash mismatch: output/b.txt" in problems
    assert "unexpected: output/extra.txt" in problems

    # A size mismatch is deterministic and avoids unnecessary hashing.
    payload["files"][1]["size"] = 999
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    assert any(problem.startswith("size mismatch: output/b.txt") for problem in verify(manifest))


def test_invalid_manifest_json_schema_and_duplicate_paths_are_rejected(tmp_path):
    manifest = tmp_path / "artifacts.json"
    manifest.write_text("{", encoding="utf-8")
    with pytest.raises(StateValidationError, match="Invalid artifact manifest JSON"):
        verify(manifest)

    _, manifest, payload = _make_snapshot(tmp_path)
    payload["schema_version"] = 999
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(StateValidationError, match="Unsupported artifact-manifest schema"):
        verify(manifest)

    payload["schema_version"] = 1
    payload["files"].append(dict(payload["files"][0]))
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(StateValidationError, match="duplicate path"):
        verify(manifest)


def test_manifest_rejects_traversal_absolute_and_windows_paths(tmp_path):
    _, manifest, payload = _make_snapshot(tmp_path)

    bad_paths = ["../secret.txt", "/etc/passwd", r"..\secret.txt", "C:/secret.txt"]
    for bad in bad_paths:
        broken = dict(payload)
        broken["files"] = [dict(payload["files"][0], path=bad)]
        manifest.write_text(json.dumps(broken), encoding="utf-8")
        with pytest.raises(UnsafePathError):
            verify(manifest)


def test_exact_verification_requires_roots(tmp_path):
    _, manifest, payload = _make_snapshot(tmp_path)
    del payload["roots"]
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    assert verify(manifest) == []
    with pytest.raises(StateValidationError, match="Exact verification requires"):
        verify(manifest, exact=True)


def test_snapshot_rejects_artifact_outside_base(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")

    with pytest.raises(UnsafePathError, match="outside base"):
        snapshot([outside], base / "manifest.json", base_dir=base)


def test_unicode_and_spaces_are_portable(tmp_path):
    output = tmp_path / "輸出 folder"
    output.mkdir()
    (output / "résumé 01.txt").write_text("ok", encoding="utf-8")
    manifest = tmp_path / "manifest.json"

    payload = snapshot([output], manifest, base_dir=tmp_path)
    assert payload["files"][0]["path"] == "輸出 folder/résumé 01.txt"
    assert verify(manifest, exact=True) == []


def test_manifest_field_validation_and_duplicate_roots(tmp_path):
    _, manifest, payload = _make_snapshot(tmp_path)

    cases = [
        ("algorithm", "md5", "Unsupported artifact hash algorithm"),
        ("files", ["not-an-object"], "file record"),
    ]
    for field, value, message in cases:
        broken = dict(payload)
        broken[field] = value
        manifest.write_text(json.dumps(broken), encoding="utf-8")
        with pytest.raises(StateValidationError, match=message):
            verify(manifest)

    broken = dict(payload)
    broken["files"] = [dict(payload["files"][0], size=-1)]
    manifest.write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(StateValidationError, match="greater than or equal"):
        verify(manifest)

    broken = dict(payload)
    broken["files"] = [dict(payload["files"][0], sha256="ABC")]
    manifest.write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(StateValidationError, match="64 lowercase hex"):
        verify(manifest)

    broken = dict(payload)
    broken["roots"] = ["output", "output"]
    manifest.write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(StateValidationError, match="duplicate root"):
        verify(manifest)


def test_snapshot_rejects_missing_inputs_empty_inputs_and_non_directory_base(tmp_path):
    manifest = tmp_path / "manifest.json"
    with pytest.raises(FileNotFoundError):
        snapshot(["missing"], manifest, base_dir=tmp_path)
    with pytest.raises(StateValidationError, match="At least one"):
        snapshot([], manifest, base_dir=tmp_path)

    base_file = tmp_path / "base.txt"
    base_file.write_text("not a directory", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        snapshot([base_file], manifest, base_dir=base_file)


def test_snapshot_accepts_single_file_and_deduplicates_inputs(tmp_path):
    artifact = tmp_path / "one.txt"
    artifact.write_text("one", encoding="utf-8")
    manifest = tmp_path / "manifest.json"

    payload = snapshot([artifact, artifact], manifest, base_dir=tmp_path)
    assert len(payload["files"]) == 1
    assert payload["files"][0]["path"] == "one.txt"
