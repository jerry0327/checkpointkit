"""Run a deterministic child-process crash-and-resume recovery demonstration."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from checkpointkit import CheckpointStore
from checkpointkit.artifacts import snapshot, verify
from checkpointkit.store import atomic_write_json

_REPORT_SCHEMA_VERSION = 1


def _prepare_root(root: Path, item_count: int) -> None:
    inputs = root / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    for index in range(item_count):
        payload = (
            f"checkpointkit deterministic recovery input\n"
            f"index={index:04d}\n"
            f"payload={'0123456789abcdef' * (index + 1)}\n"
        )
        (inputs / f"item-{index:04d}.txt").write_text(payload, encoding="utf-8", newline="\n")


def _read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            continue
        event = json.loads(line)
        if not isinstance(event, dict):
            raise RuntimeError(f"event line {line_number} is not a JSON object")
        events.append(event)
    return events


def _worker_command(
    root: Path,
    *,
    attempt: str,
    delay: float,
    pause_after: int | None = None,
) -> list[str]:
    worker = Path(__file__).with_name("crash_resume_worker.py")
    command = [
        sys.executable,
        str(worker),
        "--inputs",
        str(root / "inputs"),
        "--outputs",
        str(root / "outputs"),
        "--state",
        str(root / "checkpoint.json"),
        "--events",
        str(root / "events.jsonl"),
        "--attempt",
        attempt,
        "--delay",
        str(delay),
    ]
    if pause_after is not None:
        command.extend(
            [
                "--pause-after",
                str(pause_after),
                "--pause-file",
                str(root / "ready-to-terminate.json"),
            ]
        )
    return command


def _run_to_completion(root: Path, *, attempt: str, delay: float) -> float:
    started = time.perf_counter()
    completed = subprocess.run(_worker_command(root, attempt=attempt, delay=delay), check=False)
    elapsed = time.perf_counter() - started
    if completed.returncode != 0:
        raise RuntimeError(f"worker attempt {attempt!r} exited with {completed.returncode}")
    return elapsed


def _run_and_terminate(root: Path, *, interrupt_after: int, delay: float) -> tuple[float, int]:
    command = _worker_command(
        root,
        attempt="initial",
        delay=delay,
        pause_after=interrupt_after,
    )
    started = time.perf_counter()
    process = subprocess.Popen(command)
    ready_file = root / "ready-to-terminate.json"
    deadline = time.monotonic() + 30
    try:
        while not ready_file.is_file():
            if process.poll() is not None:
                raise RuntimeError(
                    f"worker exited with {process.returncode} before reaching interruption point"
                )
            if time.monotonic() >= deadline:
                raise TimeoutError("worker did not reach the controlled interruption point")
            time.sleep(0.01)

        ready = json.loads(ready_file.read_text(encoding="utf-8"))
        if ready != {"completed": interrupt_after, "ready_for_termination": True}:
            raise RuntimeError(f"unexpected termination handshake: {ready!r}")
        durable = CheckpointStore(root / "checkpoint.json").load()
        if len(durable["completed"]) != interrupt_after:
            raise RuntimeError("checkpoint count does not match termination handshake")

        process.terminate()
        try:
            exit_code = process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            exit_code = process.wait(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
    elapsed = time.perf_counter() - started
    if exit_code == 0:
        raise RuntimeError("controlled interruption unexpectedly exited successfully")
    return elapsed, exit_code


def _manifest_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "path": record["path"],
            "sha256": record["sha256"],
            "size": record["size"],
        }
        for record in payload["files"]
    ]


def _relative(path: Path, workspace: Path) -> str:
    return path.resolve().relative_to(workspace.resolve()).as_posix()


def run_demo(
    workspace: Path,
    *,
    item_count: int,
    interrupt_after: int,
    delay: float,
) -> dict[str, Any]:
    clean_root = workspace / "clean"
    recovered_root = workspace / "recovered"
    _prepare_root(clean_root, item_count)
    _prepare_root(recovered_root, item_count)

    clean_elapsed = _run_to_completion(clean_root, attempt="clean", delay=delay)
    initial_elapsed, interrupted_exit_code = _run_and_terminate(
        recovered_root,
        interrupt_after=interrupt_after,
        delay=delay,
    )

    interrupted_state = CheckpointStore(recovered_root / "checkpoint.json").load()
    committed_before = tuple(interrupted_state["completed"])
    resumed_elapsed = _run_to_completion(recovered_root, attempt="resumed", delay=delay)
    final_state = CheckpointStore(recovered_root / "checkpoint.json").load()

    clean_manifest_path = clean_root / "artifacts.json"
    recovered_manifest_path = recovered_root / "artifacts.json"
    clean_manifest = snapshot(["outputs"], clean_manifest_path, base_dir=clean_root)
    recovered_manifest = snapshot(["outputs"], recovered_manifest_path, base_dir=recovered_root)
    clean_problems = verify(clean_manifest_path, exact=True)
    recovered_problems = verify(recovered_manifest_path, exact=True)
    equivalent = _manifest_records(clean_manifest) == _manifest_records(recovered_manifest)

    events = _read_events(recovered_root / "events.jsonl")
    resumed_started = [
        event["key"]
        for event in events
        if event.get("attempt") == "resumed" and event.get("event") == "start"
    ]
    resumed_skipped = [
        event["key"]
        for event in events
        if event.get("attempt") == "resumed" and event.get("event") == "skip"
    ]
    resumed_completed = [
        event
        for event in events
        if event.get("attempt") == "resumed" and event.get("event") == "complete"
    ]
    complete_events = [event for event in events if event.get("event") == "complete"]
    started_counts = Counter(
        event["key"] for event in events if event.get("event") == "start"
    )
    duplicate_committed = sorted(set(committed_before).intersection(resumed_started))

    report: dict[str, Any] = {
        "schema_version": _REPORT_SCHEMA_VERSION,
        "scenario": "local-child-process-crash-and-resume",
        "total_items": item_count,
        "controlled_interrupt_after": interrupt_after,
        "interrupted_exit_code": interrupted_exit_code,
        "items_completed_before_interruption": len(committed_before),
        "items_skipped_on_resume": len(resumed_skipped),
        "items_processed_after_resume": len(resumed_completed),
        "duplicate_processing_count": len(duplicate_committed),
        "duplicate_committed_items": duplicate_committed,
        "attempted_more_than_once": sorted(
            key for key, count in started_counts.items() if count > 1
        ),
        "checkpoint_generation_history": [
            event["generation"] for event in complete_events
        ],
        "final_checkpoint_generation": final_state["generation"],
        "artifact_verification": {
            "clean_ok": not clean_problems,
            "recovered_ok": not recovered_problems,
            "equivalent_to_clean_run": equivalent,
            "clean_problems": clean_problems,
            "recovered_problems": recovered_problems,
        },
        "elapsed_seconds": {
            "clean": round(clean_elapsed, 6),
            "initial_before_termination": round(initial_elapsed, 6),
            "resumed": round(resumed_elapsed, 6),
        },
        "runtime": {
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "evidence": {
            "clean_manifest": _relative(clean_manifest_path, workspace),
            "recovered_checkpoint": _relative(
                recovered_root / "checkpoint.json", workspace
            ),
            "recovered_events": _relative(recovered_root / "events.jsonl", workspace),
            "recovered_manifest": _relative(recovered_manifest_path, workspace),
        },
        "limitations": [
            "This validates workflow-level recovery, not process-memory restoration.",
            "It does not prove exactly-once behavior for arbitrary external side effects.",
            (
                "Local locking guarantees apply only to cooperating processes on "
                "tested local filesystems."
            ),
        ],
    }

    expected_history = list(range(1, item_count + 1))
    failures = []
    if len(committed_before) != interrupt_after:
        failures.append("controlled interruption count changed")
    if len(resumed_skipped) != interrupt_after:
        failures.append("resume did not skip every committed item")
    if len(resumed_completed) != item_count - interrupt_after:
        failures.append("resume did not process exactly the remaining items")
    if duplicate_committed:
        failures.append("a committed item was processed again")
    if final_state["generation"] != item_count:
        failures.append("final checkpoint generation does not match item count")
    if report["checkpoint_generation_history"] != expected_history:
        failures.append("checkpoint generation history is not monotonic and complete")
    if clean_problems or recovered_problems or not equivalent:
        failures.append("final artifact verification failed")
    if failures:
        raise RuntimeError("; ".join(failures))
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path(".checkpointkit-demo"))
    parser.add_argument("--items", type=int, default=16)
    parser.add_argument("--interrupt-after", type=int, default=5)
    parser.add_argument("--delay", type=float, default=0.02)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--reset", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.items < 2:
        parser.error("--items must be at least 2")
    if not 1 <= args.interrupt_after < args.items:
        parser.error("--interrupt-after must be between 1 and items - 1")
    if args.delay < 0:
        parser.error("--delay must be non-negative")

    workspace = args.workspace.resolve()
    if workspace.exists():
        if not args.reset:
            parser.error(f"workspace already exists; pass --reset to replace it: {workspace}")
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)

    report = run_demo(
        workspace,
        item_count=args.items,
        interrupt_after=args.interrupt_after,
        delay=args.delay,
    )
    report_path = (args.report or (workspace / "recovery-report.json")).resolve()
    atomic_write_json(report_path, report)
    print(
        "recovery demo passed: "
        f"completed_before={report['items_completed_before_interruption']} "
        f"skipped={report['items_skipped_on_resume']} "
        f"processed_after={report['items_processed_after_resume']} "
        f"duplicates={report['duplicate_processing_count']}"
    )
    print(f"report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
