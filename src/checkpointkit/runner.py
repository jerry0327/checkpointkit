"""Command attempt recording and restart support."""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .store import atomic_write_json

RUN_SCHEMA_VERSION = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", name.strip()).strip("-.")
    if not cleaned:
        raise ValueError("Run name must contain at least one safe character")
    return cleaned


def run_state_path(state_dir: str | os.PathLike[str], name: str) -> Path:
    return Path(state_dir) / "runs" / f"{_safe_name(name)}.json"


def load_run(state_dir: str | os.PathLike[str], name: str) -> dict[str, Any]:
    path = run_state_path(state_dir, name)
    if not path.exists():
        raise FileNotFoundError(f"No recorded run named {name!r}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid run state JSON: {path}") from exc
    if payload.get("schema_version") != RUN_SCHEMA_VERSION:
        raise ValueError("Unsupported run-state schema")
    return payload


def run_command(
    name: str,
    command: Sequence[str],
    *,
    state_dir: str | os.PathLike[str] = ".checkpointkit",
    cwd: str | os.PathLike[str] | None = None,
    force: bool = False,
) -> int:
    if not command:
        raise ValueError("Command cannot be empty")

    path = run_state_path(state_dir, name)
    command_list = [str(part) for part in command]
    cwd_value = str(Path(cwd).resolve()) if cwd is not None else str(Path.cwd().resolve())

    if path.exists():
        payload = load_run(state_dir, name)
        if payload["command"] != command_list:
            raise ValueError(
                "Recorded command differs from the requested command. "
                "Use a different run name or remove the old run state."
            )
        if payload.get("status") == "completed" and not force:
            return 0
    else:
        now = _now()
        payload = {
            "schema_version": RUN_SCHEMA_VERSION,
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
    }
    payload["attempts"].append(attempt)
    payload["status"] = "running"
    payload["updated_at"] = _now()
    atomic_write_json(path, payload)

    try:
        completed = subprocess.run(command_list, cwd=cwd_value, check=False)
    except KeyboardInterrupt:
        attempt["finished_at"] = _now()
        attempt["status"] = "interrupted"
        payload["status"] = "interrupted"
        payload["updated_at"] = _now()
        atomic_write_json(path, payload)
        raise
    except BaseException:
        attempt["finished_at"] = _now()
        attempt["status"] = "error"
        payload["status"] = "error"
        payload["updated_at"] = _now()
        atomic_write_json(path, payload)
        raise

    attempt["finished_at"] = _now()
    attempt["exit_code"] = completed.returncode
    attempt["status"] = "completed" if completed.returncode == 0 else "failed"
    payload["status"] = attempt["status"]
    payload["updated_at"] = _now()
    atomic_write_json(path, payload)
    return completed.returncode


def resume_command(
    name: str,
    *,
    state_dir: str | os.PathLike[str] = ".checkpointkit",
    force: bool = False,
) -> int:
    payload = load_run(state_dir, name)
    return run_command(
        name,
        payload["command"],
        state_dir=state_dir,
        cwd=payload["cwd"],
        force=force,
    )
