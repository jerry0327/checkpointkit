import json
import sys

import pytest

from checkpointkit import StateConflictError, StateValidationError
from checkpointkit.runner import list_runs, load_run, resume_command, run_command


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
    assert payload["attempts"][0]["pid"] > 0
    assert payload["attempts"][0]["hostname"]

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


def test_stale_running_attempt_is_marked_abandoned_before_resume(tmp_path):
    state_dir = tmp_path / ".checkpointkit"
    assert run_command(
        "stale",
        [sys.executable, "-c", "pass"],
        state_dir=state_dir,
        cwd=tmp_path,
    ) == 0

    path = state_dir / "runs" / "stale.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["status"] = "running"
    payload["attempts"][0]["status"] = "running"
    payload["attempts"][0]["finished_at"] = None
    payload["attempts"][0]["exit_code"] = None
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert resume_command("stale", state_dir=state_dir) == 0
    recovered = load_run(state_dir, "stale")
    assert recovered["attempts"][0]["status"] == "abandoned"
    assert recovered["attempts"][0]["recovered_at"]
    assert recovered["attempts"][1]["status"] == "completed"


def test_existing_name_rejects_command_and_cwd_conflicts(tmp_path):
    state_dir = tmp_path / ".checkpointkit"
    command = [sys.executable, "-c", "pass"]
    assert run_command("same", command, state_dir=state_dir, cwd=tmp_path) == 0

    with pytest.raises(StateConflictError, match="command differs"):
        run_command(
            "same",
            [sys.executable, "-c", "print('different')"],
            state_dir=state_dir,
            cwd=tmp_path,
            force=True,
        )

    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(StateConflictError, match="working directory differs"):
        run_command(
            "same",
            command,
            state_dir=state_dir,
            cwd=other,
            force=True,
        )


def test_spawn_error_is_recorded(tmp_path):
    state_dir = tmp_path / ".checkpointkit"
    with pytest.raises(FileNotFoundError):
        run_command(
            "missing",
            [str(tmp_path / "does-not-exist")],
            state_dir=state_dir,
            cwd=tmp_path,
        )

    payload = load_run(state_dir, "missing")
    assert payload["status"] == "error"
    assert payload["attempts"][0]["status"] == "error"
    assert payload["attempts"][0]["error_type"] == "FileNotFoundError"


def test_invalid_attempt_shape_is_rejected(tmp_path):
    state_dir = tmp_path / ".checkpointkit"
    assert run_command(
        "bad-state",
        [sys.executable, "-c", "pass"],
        state_dir=state_dir,
        cwd=tmp_path,
    ) == 0
    path = state_dir / "runs" / "bad-state.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["attempts"][0]["number"] = 9
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(StateValidationError, match="consecutive"):
        load_run(state_dir, "bad-state")


def test_list_runs_is_sorted_and_validated(tmp_path):
    state_dir = tmp_path / ".checkpointkit"
    for name in ["zeta", "alpha"]:
        assert run_command(
            name,
            [sys.executable, "-c", "pass"],
            state_dir=state_dir,
            cwd=tmp_path,
        ) == 0

    assert [item["name"] for item in list_runs(state_dir)] == ["alpha", "zeta"]


def test_force_reruns_completed_command(tmp_path):
    state_dir = tmp_path / ".checkpointkit"
    command = [sys.executable, "-c", "pass"]
    assert run_command("force", command, state_dir=state_dir, cwd=tmp_path) == 0
    assert run_command(
        "force",
        command,
        state_dir=state_dir,
        cwd=tmp_path,
        force=True,
    ) == 0
    assert len(load_run(state_dir, "force")["attempts"]) == 2


def test_empty_command_and_unsafe_name_are_rejected(tmp_path):
    with pytest.raises(StateValidationError, match="Command cannot be empty"):
        run_command("empty", [], state_dir=tmp_path)
    with pytest.raises(StateValidationError, match="safe character"):
        run_command("...", [sys.executable], state_dir=tmp_path)


def test_run_state_schema_name_status_and_attempt_invariants(tmp_path):
    state_dir = tmp_path / ".checkpointkit"
    assert run_command(
        "invariants",
        [sys.executable, "-c", "pass"],
        state_dir=state_dir,
        cwd=tmp_path,
    ) == 0
    path = state_dir / "runs" / "invariants.json"
    original = json.loads(path.read_text(encoding="utf-8"))

    mutations = [
        ({"schema_version": 999}, "Unsupported run-state schema"),
        ({"name": "different"}, "does not match requested name"),
        ({"status": "unknown"}, "Unsupported run status"),
        ({"command": []}, "command.*cannot be empty"),
    ]
    for changes, message in mutations:
        payload = dict(original)
        payload.update(changes)
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(StateValidationError, match=message):
            load_run(state_dir, "invariants")


def test_attempt_status_invariants_are_rejected(tmp_path):
    state_dir = tmp_path / ".checkpointkit"
    assert run_command(
        "attempts",
        [sys.executable, "-c", "pass"],
        state_dir=state_dir,
        cwd=tmp_path,
    ) == 0
    path = state_dir / "runs" / "attempts.json"
    original = json.loads(path.read_text(encoding="utf-8"))

    def expect_attempt_error(changes, message, top_status=None):
        payload = json.loads(json.dumps(original))
        payload["attempts"][0].update(changes)
        if top_status is not None:
            payload["status"] = top_status
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(StateValidationError, match=message):
            load_run(state_dir, "attempts")

    expect_attempt_error({"status": "unknown"}, "Unsupported attempt status")
    expect_attempt_error(
        {"status": "running"},
        "running attempt cannot be finished",
        "running",
    )
    expect_attempt_error({"status": "error", "finished_at": None}, "terminal attempt")
    expect_attempt_error({"status": "completed", "exit_code": 3}, "exit_code 0")
    expect_attempt_error({"status": "failed", "exit_code": 0}, "non-zero exit_code")
    expect_attempt_error(
        {"status": "running", "finished_at": None, "exit_code": None},
        "inconsistent",
    )


def test_negative_return_code_records_signal(tmp_path, monkeypatch):
    state_dir = tmp_path / ".checkpointkit"

    class Completed:
        returncode = -15

    def fake_run(*args, **kwargs):
        return Completed()

    monkeypatch.setattr("checkpointkit.runner.subprocess.run", fake_run)
    assert run_command(
        "signal",
        [sys.executable, "-c", "pass"],
        state_dir=state_dir,
        cwd=tmp_path,
    ) == -15
    attempt = load_run(state_dir, "signal")["attempts"][0]
    assert attempt["signal"] == 15


def test_keyboard_interrupt_is_recorded(tmp_path, monkeypatch):
    state_dir = tmp_path / ".checkpointkit"

    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr("checkpointkit.runner.subprocess.run", interrupt)
    with pytest.raises(KeyboardInterrupt):
        run_command(
            "interrupt",
            [sys.executable, "-c", "pass"],
            state_dir=state_dir,
            cwd=tmp_path,
        )
    assert load_run(state_dir, "interrupt")["status"] == "interrupted"
