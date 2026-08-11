"""Command attempt recording and restart support."""

from __future__ import annotations

import copy
import os
import re
import socket
import subprocess
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._validation import (
    load_json_object,
    require_integer,
    require_list,
    require_string,
    require_timestamp,
)
from .errors import StateConflictError, StateValidationError
from .locking import FileLock, lock_path_for
from .store import atomic_write_json

RUN_SCHEMA_VERSION = 1
_RUN_KIND = "run state"
_RUN_STATUSES = {"new", "running", "completed", "failed", "interrupted", "error"}
_ATTEMPT_STATUSES = {"running", "completed", "failed", "interrupted", "error", "abandoned"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(name: str) -> str:
    require_string(name, field="name", kind=_RUN_KIND)
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", name.strip()).strip("-.")
    if not cleaned:
        raise StateValidationError("Run name must contain at least one safe character")
    return cleaned


def run_state_path(state_dir: str | os.PathLike[str], name: str) -> Path:
    return Path(state_dir) / "runs" / f"{_safe_name(name)}.json"


def _generation(payload: dict[str, Any]) -> int:
    return require_integer(
        payload.get("generation", 0),
        field="generation",
        kind=_RUN_KIND,
        minimum=0,
    )


def validate_run_state(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != RUN_SCHEMA_VERSION:
        raise StateValidationError(
            f"Unsupported run-state schema {payload.get('schema_version')!r}; "
            f"expected {RUN_SCHEMA_VERSION}"
        )

    if "generation" in payload:
        _generation(payload)
    require_string(payload.get("name"), field="name", kind=_RUN_KIND)
    command = require_list(payload.get("command"), field="command", kind=_RUN_KIND)
    if not command:
        raise StateValidationError("run state field 'command' cannot be empty")
    for index, part in enumerate(command):
        require_string(
            part,
            field=f"command[{index}]",
            kind=_RUN_KIND,
            allow_empty=index > 0,
        )
    require_string(payload.get("cwd"), field="cwd", kind=_RUN_KIND)
    require_timestamp(payload.get("created_at"), field="created_at", kind=_RUN_KIND)
    require_timestamp(payload.get("updated_at"), field="updated_at", kind=_RUN_KIND)

    status = require_string(payload.get("status"), field="status", kind=_RUN_KIND)
    if status not in _RUN_STATUSES:
        raise StateValidationError(f"Unsupported run status: {status!r}")

    attempts = require_list(payload.get("attempts"), field="attempts", kind=_RUN_KIND)
    running_attempts = 0
    for index, raw_attempt in enumerate(attempts):
        if not isinstance(raw_attempt, dict):
            raise StateValidationError(f"run state attempt {index + 1} must be an object")
        attempt = raw_attempt
        number = require_integer(
            attempt.get("number"),
            field=f"attempts[{index}].number",
            kind=_RUN_KIND,
            minimum=1,
        )
        if number != index + 1:
            raise StateValidationError("run-state attempt numbers must be consecutive")
        require_timestamp(
            attempt.get("started_at"),
            field=f"attempts[{index}].started_at",
            kind=_RUN_KIND,
        )
        attempt_status = require_string(
            attempt.get("status"),
            field=f"attempts[{index}].status",
            kind=_RUN_KIND,
        )
        if attempt_status not in _ATTEMPT_STATUSES:
            raise StateValidationError(f"Unsupported attempt status: {attempt_status!r}")

        finished_at = attempt.get("finished_at")
        exit_code = attempt.get("exit_code")
        if finished_at is not None:
            require_timestamp(
                finished_at,
                field=f"attempts[{index}].finished_at",
                kind=_RUN_KIND,
            )
        if exit_code is not None:
            require_integer(
                exit_code,
                field=f"attempts[{index}].exit_code",
                kind=_RUN_KIND,
            )
        if "pid" in attempt:
            require_integer(
                attempt["pid"],
                field=f"attempts[{index}].pid",
                kind=_RUN_KIND,
                minimum=1,
            )
        if "hostname" in attempt:
            require_string(
                attempt["hostname"],
                field=f"attempts[{index}].hostname",
                kind=_RUN_KIND,
            )
        if "recovered_at" in attempt:
            require_timestamp(
                attempt["recovered_at"],
                field=f"attempts[{index}].recovered_at",
                kind=_RUN_KIND,
            )

        if attempt_status == "running":
            running_attempts += 1
            if finished_at is not None or exit_code is not None:
                raise StateValidationError("a running attempt cannot be finished")
        elif finished_at is None:
            raise StateValidationError("a terminal attempt must include finished_at")

        if attempt_status == "completed" and exit_code != 0:
            raise StateValidationError("a completed attempt must have exit_code 0")
        if attempt_status == "failed" and (exit_code is None or exit_code == 0):
            raise StateValidationError("a failed attempt must have a non-zero exit_code")

    if running_attempts > 1:
        raise StateValidationError("run state cannot contain multiple running attempts")
    if (status == "running") != (running_attempts == 1):
        raise StateValidationError("run state status and running attempt are inconsistent")
    return payload


def _normalize_run_state(payload: dict[str, Any]) -> dict[str, Any]:
    validate_run_state(payload)
    if "generation" in payload:
        return payload
    normalized = dict(payload)
    normalized["generation"] = 0
    return normalized


def _load_run_path(path: Path) -> dict[str, Any]:
    payload = load_json_object(path, kind=_RUN_KIND)
    return _normalize_run_state(payload)


def load_run(state_dir: str | os.PathLike[str], name: str) -> dict[str, Any]:
    path = run_state_path(state_dir, name)
    if not path.exists():
        raise FileNotFoundError(f"No recorded run named {name!r}: {path}")
    payload = _load_run_path(path)
    if payload["name"] != name:
        raise StateValidationError(
            f"Run-state name {payload['name']!r} does not match requested name {name!r}"
        )
    return payload


def _write_run_unlocked(path: Path, payload: dict[str, Any]) -> None:
    actual_generation = _load_run_path(path)["generation"] if path.exists() else 0
    expected_generation = payload["generation"]
    if actual_generation != expected_generation:
        raise StateConflictError(
            f"State generation conflict for {path}: "
            f"expected {expected_generation}, found {actual_generation}"
        )

    candidate = copy.deepcopy(payload)
    candidate["schema_version"] = RUN_SCHEMA_VERSION
    candidate["generation"] = expected_generation + 1
    candidate["updated_at"] = _now()
    validate_run_state(candidate)
    atomic_write_json(path, candidate)
    payload.clear()
    payload.update(candidate)


def _abandon_running_attempt(payload: dict[str, Any]) -> bool:
    changed = False
    now = _now()
    for attempt in payload["attempts"]:
        if attempt["status"] == "running":
            attempt["status"] = "abandoned"
            attempt["finished_at"] = now
            attempt["recovered_at"] = now
            attempt["recovery_reason"] = "previous process ended before finalizing the attempt"
            changed = True
    if changed:
        payload["status"] = "interrupted"
        payload["updated_at"] = now
    return changed


def run_command(
    name: str,
    command: Sequence[str],
    *,
    state_dir: str | os.PathLike[str] = ".checkpointkit",
    cwd: str | os.PathLike[str] | None = None,
    force: bool = False,
    lock_timeout: float = 10.0,
) -> int:
    """Run a command while holding an OS-backed lease for its run name."""
    if not command:
        raise StateValidationError("Command cannot be empty")

    path = run_state_path(state_dir, name)
    command_list = [str(part) for part in command]
    if not command_list[0]:
        raise StateValidationError("Command executable cannot be empty")
    cwd_value = str(Path(cwd).resolve()) if cwd is not None else str(Path.cwd().resolve())

    with FileLock(lock_path_for(path), timeout=lock_timeout):
        if path.exists():
            payload = _load_run_path(path)
            if payload["name"] != name:
                raise StateValidationError(
                    f"Run-state name {payload['name']!r} does not match requested name {name!r}"
                )
            if payload["command"] != command_list:
                raise StateConflictError(
                    "Recorded command differs from the requested command. "
                    "Use a different run name or remove the old run state."
                )
            if payload["cwd"] != cwd_value:
                raise StateConflictError(
                    "Recorded working directory differs from the requested directory. "
                    "Use resume or a different run name."
                )
            if payload["status"] == "completed" and not force:
                return 0
            _abandon_running_attempt(payload)
        else:
            now = _now()
            payload = {
                "schema_version": RUN_SCHEMA_VERSION,
                "generation": 0,
                "name": name,
                "command": command_list,
                "cwd": cwd_value,
                "created_at": now,
                "updated_at": now,
                "status": "new",
                "attempts": [],
            }

        attempt: dict[str, Any] = {
            "number": len(payload["attempts"]) + 1,
            "started_at": _now(),
            "finished_at": None,
            "exit_code": None,
            "status": "running",
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
        }
        payload["attempts"].append(attempt)
        payload["status"] = "running"
        payload["updated_at"] = _now()
        validate_run_state(payload)
        _write_run_unlocked(path, payload)
        # The writer replaces payload with a deep-copied durable candidate, so
        # refresh the nested attempt reference before recording the outcome.
        attempt = payload["attempts"][-1]

        try:
            completed = subprocess.run(command_list, cwd=cwd_value, check=False)
        except KeyboardInterrupt:
            attempt["finished_at"] = _now()
            attempt["status"] = "interrupted"
            payload["status"] = "interrupted"
            payload["updated_at"] = _now()
            validate_run_state(payload)
            _write_run_unlocked(path, payload)
            raise
        except BaseException as exc:
            attempt["finished_at"] = _now()
            attempt["status"] = "error"
            attempt["error_type"] = type(exc).__name__
            attempt["error_message"] = str(exc)
            payload["status"] = "error"
            payload["updated_at"] = _now()
            validate_run_state(payload)
            _write_run_unlocked(path, payload)
            raise

        attempt["finished_at"] = _now()
        attempt["exit_code"] = completed.returncode
        attempt["status"] = "completed" if completed.returncode == 0 else "failed"
        if completed.returncode < 0:
            attempt["signal"] = -completed.returncode
        payload["status"] = attempt["status"]
        payload["updated_at"] = _now()
        validate_run_state(payload)
        _write_run_unlocked(path, payload)
        return completed.returncode


def resume_command(
    name: str,
    *,
    state_dir: str | os.PathLike[str] = ".checkpointkit",
    force: bool = False,
    lock_timeout: float = 10.0,
) -> int:
    payload = load_run(state_dir, name)
    return run_command(
        name,
        payload["command"],
        state_dir=state_dir,
        cwd=payload["cwd"],
        force=force,
        lock_timeout=lock_timeout,
    )


def list_runs(state_dir: str | os.PathLike[str] = ".checkpointkit") -> list[dict[str, Any]]:
    """Return validated run states sorted by run name."""
    runs_dir = Path(state_dir) / "runs"
    if not runs_dir.exists():
        return []
    runs: list[dict[str, Any]] = []
    for path in sorted(runs_dir.glob("*.json")):
        runs.append(_load_run_path(path))
    return sorted(runs, key=lambda item: item["name"])
