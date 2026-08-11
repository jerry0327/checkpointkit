# CheckpointKit

[![CI](https://github.com/jerry0327/checkpointkit/actions/workflows/ci.yml/badge.svg)](https://github.com/jerry0327/checkpointkit/actions/workflows/ci.yml)

**Fault-tolerant checkpointing and resume primitives for long-running AI, data, and batch jobs.**

CheckpointKit is a local-first Python toolkit for work that should survive ordinary interruptions without restarting from zero. It targets transcription, OCR, model evaluation, data conversion, scraping, media processing, and other batch pipelines that may run for minutes or hours.

> **Status: alpha (`0.2.0a1`).** Local coordination is tested on supported CI platforms, but the public API and durable JSON formats may still change before 1.0.

## Why CheckpointKit

Long-running jobs fail for routine reasons: a runner is reclaimed, a notebook disconnects, a process crashes, a machine reboots, or one input is malformed. Without durable progress metadata, recovery becomes guesswork and completed work gets repeated.

CheckpointKit provides small, inspectable primitives rather than a hidden scheduler:

- atomic, human-readable JSON checkpoint state;
- strict validation that fails closed on malformed or unsupported state;
- item-level completion tracking for resumable batches;
- monotonic generations that reject stale in-memory writes;
- cross-platform advisory locks for cooperating writers on ordinary local filesystems;
- command attempt history with a per-run lease and stale-attempt recovery;
- artifact snapshots with SHA-256 verification and optional exact-file checks;
- stable CLI errors suitable for scripts and operators;
- a dependency-free runtime core with typed public APIs.

The intended workflow is:

```text
run -> checkpoint -> interruption -> inspect -> resume -> verify
```

## Install for development

CheckpointKit is not published to PyPI yet. Install the current source tree with Python 3.10 or newer:

```bash
git clone https://github.com/jerry0327/checkpointkit.git
cd checkpointkit
python -m venv .venv
# Activate .venv for your shell, then:
python -m pip install -e ".[dev]"
```

## CLI

Wrap a command and record durable attempt metadata:

```bash
checkpointkit run --name transcribe -- python pipeline.py
checkpointkit status --name transcribe
checkpointkit list
checkpointkit resume --name transcribe
```

A run-name lease is held for the lifetime of the wrapped command. A second cooperating wrapper using the same state directory and name waits up to 10 seconds by default, then exits with an error. Set an intentional timeout when needed:

```bash
checkpointkit run --name transcribe --lock-timeout 30 -- python pipeline.py
checkpointkit resume --name transcribe --lock-timeout 30
```

A completed command is not rerun unless `--force` is supplied. If a prior wrapper disappeared while an attempt was recorded as `running`, the next lease holder preserves that attempt as `abandoned` before starting a new attempt.

Snapshot output artifacts and verify them later:

```bash
checkpointkit snapshot output/ --manifest artifacts.json
checkpointkit verify artifacts.json
checkpointkit verify artifacts.json --exact
checkpointkit verify artifacts.json --exact --json
```

Normal verification checks every recorded file for existence, byte size, and SHA-256 digest. `--exact` also reports files added beneath the original snapshot roots.

`resume` reruns the recorded command. Fine-grained recovery comes from the workload itself recording meaningful progress with `CheckpointStore`.

## Python API

The high-level item methods acquire a sidecar OS lock, reload current state, apply one mutation, and atomically install the next generation:

```python
from checkpointkit import CheckpointStore

store = CheckpointStore(".checkpointkit/transcribe.json")

for item in inputs:
    key = str(item.id)
    if store.is_complete(key):
        continue

    process(item)
    store.mark_complete(key, {"output": f"out/{key}.json"})
```

Additional helpers support rollback and scheduling:

```python
store.mark_incomplete("item-17")
pending = store.pending_keys(["item-16", "item-17", "item-18"])
```

For a custom read-modify-write operation, the payload returned by `load()` includes the observed generation. `save()` uses that value as a compare-and-swap token and returns the newly written state:

```python
from checkpointkit import StateConflictError

payload = store.load()
payload["metadata"]["model"] = "example-v2"

try:
    saved = store.save(payload)
    print(saved["generation"])
except StateConflictError:
    # Another writer committed first. Reload and deliberately reapply the change.
    raise
```

Legacy schema-1 checkpoint and run-state documents without `generation` remain readable as generation `0`. A read alone does not rewrite them; the next successful write stores generation `1`.

Checkpoint writes use a temporary file in the destination directory, flush and fsync it, then replace the old state with `os.replace`. If serialization, replacement, lock acquisition, or generation validation fails, a newer valid checkpoint is not silently overwritten.

## Failure and security model

CheckpointKit rejects truncated JSON, unsupported schema versions, invalid field types, duplicate completion keys, duplicate manifest paths, unsafe artifact paths, inconsistent run attempts, and stale generation tokens. Artifact records cannot use absolute paths, drive prefixes, backslashes, or `..`, and symlink resolution cannot escape the declared base directory.

Checkpoint files and lock sidecars can reveal command lines, paths, identifiers, and operational timing. Treat the state directory as sensitive operational data. See [`docs/failure-model.md`](docs/failure-model.md), [`docs/concurrency.md`](docs/concurrency.md), and [`SECURITY.md`](SECURITY.md).

## What CheckpointKit is not

CheckpointKit is **not** operating-system process-memory checkpoint/restore. It does not freeze an arbitrary program and continue at the exact CPU instruction where it stopped. It provides application- and workflow-level recovery primitives; the workload defines what “completed” means.

Local coordination applies only to **cooperating CheckpointKit writers on tested ordinary local filesystems**. Advisory locks can be bypassed, and network filesystems or object-store mounts may have different lock and rename semantics. CheckpointKit does not claim distributed transactions or exactly-once execution of arbitrary external side effects.

A command can finish its external work and then lose power before its terminal status is written. Use idempotency keys or a domain-specific transaction protocol for irreversible external operations.

## Platform support

CI exercises the complete suite on Python 3.10–3.14 on Linux and Python 3.14 on current Windows and macOS hosted runners. The same generation, lock-timeout, process-exit, and stale-writer semantics are tested across those platforms. Unsupported filesystem behavior is documented rather than assumed equivalent.

## Examples

Interrupt and rerun the basic batch example; completed items are skipped:

```bash
python examples/resumable_batch.py
```

Run several cooperating processes against one checkpoint and inspect the merged generation history:

```bash
python examples/concurrent_workers.py
```

The concurrency example demonstrates durable progress coordination, not exactly-once application side effects.

## Development

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest --cov=checkpointkit --cov-report=term-missing --cov-branch
python -m build
```

The test suite enforces at least 90% branch-aware coverage in CI.

## Roadmap and contributing

Current priorities are in [`ROADMAP.md`](ROADMAP.md). Bug reports, focused proposals, documentation fixes, tests, and pull requests are welcome. Start with [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`docs/design.md`](docs/design.md).

Security-sensitive reports should follow [`SECURITY.md`](SECURITY.md).

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
