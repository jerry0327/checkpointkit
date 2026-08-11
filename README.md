# CheckpointKit

[![CI](https://github.com/jerry0327/checkpointkit/actions/workflows/ci.yml/badge.svg)](https://github.com/jerry0327/checkpointkit/actions/workflows/ci.yml)

**Fault-tolerant checkpointing and resume primitives for long-running AI, data, and batch jobs.**

CheckpointKit is a local-first Python toolkit for jobs that should survive ordinary interruptions without forcing you to restart from zero. It targets workloads such as transcription, OCR, model evaluation, data conversion, scraping, media processing, and other batch pipelines that may run for minutes or hours.

> **Status: pre-alpha (`0.1.0a0`).** The project is usable for experimentation, but the public API and checkpoint format may still change before the first stable release.

## The problem

Long-running jobs fail for boring reasons: a runner is reclaimed, a notebook disconnects, a process crashes, a machine reboots, or a single input is malformed. Without durable progress metadata, recovery becomes guesswork and expensive work gets repeated.

CheckpointKit focuses on a small set of explicit recovery primitives:

- atomic, human-readable JSON checkpoint state;
- item-level completion tracking for resumable batches;
- command attempt history for interrupted jobs;
- artifact snapshots with SHA-256 verification;
- inspectable status instead of hidden scheduler state;
- a dependency-free local core.

The intended workflow is:

```text
run -> checkpoint -> interruption -> inspect -> resume -> verify
```

## Install for development

CheckpointKit is not published to PyPI yet. Install the current source tree with Python 3.10+:

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
checkpointkit resume --name transcribe
```

Snapshot output artifacts and verify them later:

```bash
checkpointkit snapshot output/ --manifest artifacts.json
checkpointkit verify artifacts.json
```

`resume` reruns the recorded command. Fine-grained recovery comes from the workload itself recording meaningful progress, for example with `CheckpointStore`.

## Python API

```python
from checkpointkit import CheckpointStore

store = CheckpointStore(".checkpointkit/transcribe.json")

for item in inputs:
    key = str(item.id)
    if store.is_complete(key):
        continue

    process(item)
    store.mark_complete(key)
```

Checkpoint writes use a temporary file plus `os.replace`, so an interrupted write is not treated as a valid new checkpoint.

## What CheckpointKit is not

CheckpointKit is **not** operating-system process-memory checkpoint/restore. It does not claim to freeze an arbitrary program and continue at the exact CPU instruction where it stopped. It provides application- and workflow-level recovery primitives. The workload must define what “completed” means.

The initial local backend also does not provide multi-process locking. Concurrent writers to the same checkpoint file are intentionally out of scope until a locking/transaction design is specified and tested.

## Example

See [`examples/resumable_batch.py`](examples/resumable_batch.py) for a minimal batch that can be interrupted and rerun without repeating completed items.

## Development

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest
```

CI runs lint and tests on Python 3.10 through 3.13.

## Roadmap

Current priorities are documented in [`ROADMAP.md`](ROADMAP.md). The first milestone is deliberately narrow: make local checkpoint state, resumable batches, command attempts, and artifact verification boring and reliable before adding remote backends.

## Contributing

Bug reports, focused feature proposals, documentation fixes, tests, and pull requests are welcome. Start with [`CONTRIBUTING.md`](CONTRIBUTING.md) and the design notes in [`docs/design.md`](docs/design.md).

Security-sensitive reports should follow [`SECURITY.md`](SECURITY.md).

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
