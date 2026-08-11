from checkpointkit.artifacts import snapshot, verify


def test_snapshot_and_verify(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    (output / "a.txt").write_text("alpha", encoding="utf-8")
    (output / "b.txt").write_text("beta", encoding="utf-8")
    manifest = tmp_path / "artifacts.json"

    payload = snapshot(["output"], manifest, base_dir=tmp_path)

    assert [item["path"] for item in payload["files"]] == ["output/a.txt", "output/b.txt"]
    assert verify(manifest) == []

    (output / "a.txt").write_text("changed", encoding="utf-8")
    problems = verify(manifest)
    assert len(problems) == 1
    assert "mismatch" in problems[0]
