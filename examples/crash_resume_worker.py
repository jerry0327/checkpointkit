"""Worker used by the reproducible crash-and-resume reference workload."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from checkpointkit import CheckpointStore


def _append_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _write_pause_file(path: Path, completed: int) -> None:
    _atomic_write_json(path, {"completed": completed, "ready_for_termination": True})


def process_batch(
    *,
    inputs: Path,
    outputs: Path,
    state: Path,
    events: Path,
    attempt: str,
    delay: float,
    pause_after: int | None,
    pause_file: Path | None,
) -> None:
    store = CheckpointStore(state)
    input_paths = sorted(path for path in inputs.glob("*.txt") if path.is_file())
    if not input_paths:
        raise RuntimeError(f"No input files found in {inputs}")

    outputs.mkdir(parents=True, exist_ok=True)
    for input_path in input_paths:
        key = input_path.name
        if store.is_complete(key):
            _append_event(events, {"attempt": attempt, "event": "skip", "key": key})
            continue

        _append_event(events, {"attempt": attempt, "event": "start", "key": key})
        if delay:
            time.sleep(delay)

        source = input_path.read_bytes()
        input_digest = hashlib.sha256(source).hexdigest()
        result_digest = hashlib.sha256(b"checkpointkit-demo\0" + source).hexdigest()
        output_path = outputs / f"{input_digest}.json"
        _atomic_write_json(
            output_path,
            {
                "bytes": len(source),
                "input": key,
                "input_sha256": input_digest,
                "result_sha256": result_digest,
            },
        )
        store.mark_complete(
            key,
            {
                "output": output_path.name,
                "result_sha256": result_digest,
            },
        )
        durable = store.load()
        completed = len(durable["completed"])
        _append_event(
            events,
            {
                "attempt": attempt,
                "event": "complete",
                "generation": durable["generation"],
                "key": key,
                "output": output_path.name,
            },
        )

        if pause_after is not None and completed == pause_after:
            if pause_file is None:
                raise RuntimeError("pause_file is required when pause_after is set")
            _write_pause_file(pause_file, completed)
            _append_event(
                events,
                {
                    "attempt": attempt,
                    "completed": completed,
                    "event": "paused",
                },
            )
            while True:
                time.sleep(60)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--outputs", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--delay", type=float, default=0.02)
    parser.add_argument("--pause-after", type=int)
    parser.add_argument("--pause-file", type=Path)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.delay < 0:
        parser.error("--delay must be non-negative")
    if args.pause_after is not None and args.pause_after < 1:
        parser.error("--pause-after must be positive")
    process_batch(
        inputs=args.inputs,
        outputs=args.outputs,
        state=args.state,
        events=args.events,
        attempt=args.attempt,
        delay=args.delay,
        pause_after=args.pause_after,
        pause_file=args.pause_file,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
