"""Run cooperating processes against one CheckpointStore.

This example demonstrates durable progress coordination. The simulated work is
idempotent; real external side effects still need domain-specific idempotency or
transactions.
"""

from __future__ import annotations

import argparse
import multiprocessing
import time
from pathlib import Path

from checkpointkit import CheckpointStore


def worker(state_path: str, keys: list[str], delay: float) -> None:
    store = CheckpointStore(state_path, lock_timeout=10.0)
    for key in keys:
        if store.is_complete(key):
            continue
        time.sleep(delay)
        store.mark_complete(key, {"worker_pid": multiprocessing.current_process().pid})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default=".checkpointkit/concurrent-example.json")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--items-per-worker", type=int, default=5)
    parser.add_argument("--delay", type=float, default=0.02)
    args = parser.parse_args()

    if args.workers < 1 or args.items_per_worker < 1:
        parser.error("workers and items-per-worker must be positive")

    state_path = str(Path(args.state))
    context = multiprocessing.get_context("spawn")
    processes = []
    for worker_index in range(args.workers):
        keys = [
            f"worker-{worker_index}-item-{item_index}"
            for item_index in range(args.items_per_worker)
        ]
        processes.append(
            context.Process(target=worker, args=(state_path, keys, args.delay))
        )

    for process in processes:
        process.start()
    for process in processes:
        process.join()
        if process.exitcode != 0:
            raise SystemExit(f"worker {process.pid} exited with {process.exitcode}")

    payload = CheckpointStore(state_path).load()
    print(f"completed={len(payload['completed'])}")
    print(f"generation={payload['generation']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
