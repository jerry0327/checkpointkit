# CheckpointKit

[![CI](https://github.com/jerry0327/checkpointkit/actions/workflows/ci.yml/badge.svg)](https://github.com/jerry0327/checkpointkit/actions/workflows/ci.yml)

**Fault-tolerant checkpointing and resume primitives for long-running AI, data, and batch jobs.**

CheckpointKit is a local-first Python toolkit for work that should survive ordinary interruptions without restarting from zero. It targets transcription, OCR, model evaluation, data conversion, scraping, media processing, and other batch pipelines that may run for minutes or hours.

> **Status: alpha (`0.1.0a1`).** The core recovery behavior is tested, but the public API and durable JSON formats may still change before 1.0.

## Why CheckpointKit

Long-running jobs fail for routine reasons: a runner is reclaimed, a notebook disconnects, a process crashes, a machine reboots, or one input is malformed. Without durable progress metadata, recovery becomes guesswork and completed work gets repeated.

CheckpointKit provides small, inspectable primitives rather than a hidden scheduler:

- atomic, human-readable JSON checkpoint state;
- strict validation that fails closed on malformed or unsupported state;
- item-level completion tracking for resumable batches;
- command attempt history with stale `running` attempts marked `abandoned` on resume;
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

A completed command is not rerun unless `--force` is supplied. If a prior process disappeared while an attempt was recorded as `running`, the next run or resume preserves that attempt as `abandoned` before starting a new attempt.

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

Checkpoint writes use a temporary file in the destination directory, flush and fsync it, then replace the old state with `os.replace`. If serialization or replacement fails, the previous valid checkpoint remains in place and the temporary file is removed.

## Failure and security model

CheckpointKit rejects truncated JSON, unsupported schema versions, invalid field types, duplicate completion keys, duplicate manifest paths, unsafe artifact paths, and inconsistent run-attempt state. Artifact records cannot use absolute paths, drive prefixes, backslashes, or `..`, and symlink resolution cannot escape the declared base directory.

Checkpoint files can still contain sensitive command lines, paths, identifiers, and metadata. Treat them as operational records, not public logs. See [`docs/failure-model.md`](docs/failure-model.md) and [`SECURITY.md`](SECURITY.md).

## What CheckpointKit is not

CheckpointKit is **not** operating-system process-memory checkpoint/restore. It does not freeze an arbitrary program and continue at the exact CPU instruction where it stopped. It provides application- and workflow-level recovery primitives; the workload defines what “completed” means.

The local backend remains single-writer. Atomic replacement prevents torn documents but does not provide transaction isolation between concurrent writers. The accepted coordination design is documented in [`docs/concurrency.md`](docs/concurrency.md).

## Platform support

CI is configured to exercise the core suite on Python 3.10–3.14 on Linux and Python 3.14 on current Windows and macOS hosted runners. Platform-specific filesystem behavior is documented instead of being assumed identical.

## Example

See [`examples/resumable_batch.py`](examples/resumable_batch.py). Interrupt it and rerun it; completed items are skipped.

```bash
python examples/resumable_batch.py
```

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
