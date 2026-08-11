import sys

from checkpointkit.runner import load_run, resume_command, run_command


def test_run_records_success(tmp_path):
    state_dir = tmp_path / ".checkpointkit"
    code = run_command(
        "ok",
        [sys.executable, "-c", "print('ok')"],
        state_dir=state_dir,
        cwd=tmp_path,
    )

    assert code == 0
    payload = load_run(state_dir, "ok")
    assert payload["status"] == "completed"
    assert payload["attempts"][0]["exit_code"] == 0

    # A completed run is not executed again unless force=True.
    assert resume_command("ok", state_dir=state_dir) == 0
    assert len(load_run(state_dir, "ok")["attempts"]) == 1


def test_failed_run_can_be_resumed(tmp_path):
    state_dir = tmp_path / ".checkpointkit"
    code = run_command(
        "fails",
        [sys.executable, "-c", "raise SystemExit(7)"],
        state_dir=state_dir,
        cwd=tmp_path,
    )
    assert code == 7

    code = resume_command("fails", state_dir=state_dir)
    assert code == 7
    payload = load_run(state_dir, "fails")
    assert payload["status"] == "failed"
    assert len(payload["attempts"]) == 2
