import json
import sys

from checkpointkit.cli import main


def test_cli_run_status_and_list(tmp_path, capsys):
    state_dir = tmp_path / "state"
    code = main(
        [
            "run",
            "--name",
            "demo",
            "--state-dir",
            str(state_dir),
            "--",
            sys.executable,
            "-c",
            "print('demo')",
        ]
    )
    assert code == 0

    assert main(["status", "--name", "demo", "--state-dir", str(state_dir)]) == 0
    output = capsys.readouterr().out
    assert "status: completed" in output
    assert "generation: 2" in output

    assert main(["list", "--state-dir", str(state_dir), "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed[0]["name"] == "demo"
    assert listed[0]["generation"] == 2


def test_cli_forwards_lock_timeout_to_run_and_resume(monkeypatch):
    observed = {}

    def fake_run(name, command, *, state_dir, cwd, force, lock_timeout):
        observed["run"] = (name, command, state_dir, cwd, force, lock_timeout)
        return 0

    def fake_resume(name, *, state_dir, force, lock_timeout):
        observed["resume"] = (name, state_dir, force, lock_timeout)
        return 0

    monkeypatch.setattr("checkpointkit.cli.run_command", fake_run)
    monkeypatch.setattr("checkpointkit.cli.resume_command", fake_resume)

    assert main(
        [
            "run",
            "--name",
            "demo",
            "--state-dir",
            "state",
            "--lock-timeout",
            "0.25",
            "--",
            "python",
            "job.py",
        ]
    ) == 0
    assert observed["run"][-1] == 0.25

    assert main(
        [
            "resume",
            "--name",
            "demo",
            "--state-dir",
            "state",
            "--lock-timeout",
            "1.5",
        ]
    ) == 0
    assert observed["resume"][-1] == 1.5


def test_cli_verify_json_and_exact(tmp_path, capsys):
    output = tmp_path / "output"
    output.mkdir()
    (output / "a.txt").write_text("a", encoding="utf-8")
    manifest = tmp_path / "manifest.json"

    assert main(
        [
            "snapshot",
            "output",
            "--manifest",
            str(manifest),
            "--base-dir",
            str(tmp_path),
        ]
    ) == 0
    capsys.readouterr()

    assert main(["verify", str(manifest), "--exact", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {"ok": True, "problems": []}

    (output / "extra.txt").write_text("extra", encoding="utf-8")
    assert main(["verify", str(manifest), "--exact", "--json"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is False
    assert result["problems"] == ["unexpected: output/extra.txt"]


def test_cli_turns_expected_errors_into_stable_stderr(tmp_path, capsys):
    bad_manifest = tmp_path / "bad.json"
    bad_manifest.write_text("{", encoding="utf-8")

    assert main(["verify", str(bad_manifest)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("checkpointkit: error:")
    assert "Traceback" not in captured.err


def test_cli_list_empty_state(tmp_path, capsys):
    assert main(["list", "--state-dir", str(tmp_path / "state")]) == 0
    assert capsys.readouterr().out.strip() == "no recorded runs"


def test_cli_status_json_and_human_list(tmp_path, capsys):
    state_dir = tmp_path / "state"
    assert main(
        [
            "run",
            "--name",
            "json-demo",
            "--state-dir",
            str(state_dir),
            "--",
            sys.executable,
            "-c",
            "pass",
        ]
    ) == 0
    capsys.readouterr()

    assert main(
        ["status", "--name", "json-demo", "--state-dir", str(state_dir), "--json"]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "completed"
    assert payload["generation"] == 2

    assert main(["list", "--state-dir", str(state_dir)]) == 0
    assert "json-demo\tcompleted\t1 attempt(s)" in capsys.readouterr().out


def test_cli_human_verify_failure_and_success(tmp_path, capsys):
    output = tmp_path / "output"
    output.mkdir()
    artifact = output / "a.txt"
    artifact.write_text("a", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    assert main(
        [
            "snapshot",
            "output",
            "--manifest",
            str(manifest),
            "--base-dir",
            str(tmp_path),
        ]
    ) == 0
    assert "wrote" in capsys.readouterr().out

    assert main(["verify", str(manifest)]) == 0
    assert "verified:" in capsys.readouterr().out

    artifact.write_text("changed", encoding="utf-8")
    assert main(["verify", str(manifest)]) == 1
    assert "mismatch" in capsys.readouterr().out


def test_cli_keyboard_interrupt_returns_130(monkeypatch, capsys):
    def raise_interrupt(*args):
        raise KeyboardInterrupt

    monkeypatch.setattr("checkpointkit.cli._dispatch", raise_interrupt)
    assert main(["list"]) == 130
    assert capsys.readouterr().err.strip() == "checkpointkit: interrupted"
