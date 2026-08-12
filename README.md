# CheckpointKit

[![CI](https://github.com/jerry0327/checkpointkit/actions/workflows/ci.yml/badge.svg)](https://github.com/jerry0327/checkpointkit/actions/workflows/ci.yml)
[![CodeQL](https://github.com/jerry0327/checkpointkit/actions/workflows/codeql.yml/badge.svg)](https://github.com/jerry0327/checkpointkit/actions/workflows/codeql.yml)

**Crash-resilient, local-first checkpointing and resume primitives for long-running AI, data, and batch jobs.**

CheckpointKit gives Python workloads an explicit recovery layer without requiring a distributed scheduler. It records durable item progress, command-attempt history, and artifact integrity so an interrupted process can be inspected and restarted without blindly repeating completed work.

Typical workloads include transcription, OCR, model evaluation, dataset conversion, scraping, media processing, local agent pipelines, and other jobs that may run for minutes or hours.

> **Current release: `0.3.0` (beta).** The documented local recovery contract is tested across Linux, Windows, and macOS. APIs and durable formats remain pre-1.0 and may evolve with documented migration notes.

## Core capabilities

- atomic, validated JSON checkpoint state;
- item-level completion tracking and rollback;
- monotonic generations with stale-writer detection;
- advisory locks for cooperating local writers;
- per-run-name leases and ordered command attempt history;
- stale-attempt recovery after unclean process exit;
- artifact snapshots with SHA-256 and exact verification;
- stable CLI errors and typed Python APIs;
- a dependency-free runtime core.

```text
run → checkpoint → interruption → inspect → resume → verify
```

## Install

Install the verified GitHub release wheel:

```bash
python -m pip install \
  https://github.com/jerry0327/checkpointkit/releases/download/v0.3.0/checkpointkit-0.3.0-py3-none-any.whl
```

Or install the tagged source:

```bash
python -m pip install \
  "checkpointkit @ git+https://github.com/jerry0327/checkpointkit.git@v0.3.0"
```

For development:

```bash
git clone https://github.com/jerry0327/checkpointkit.git
cd checkpointkit
python -m venv .venv
# Activate .venv, then:
python -m pip install -e ".[dev]"
```

Python 3.10 through 3.14 is supported.

## CLI

```bash
checkpointkit run --name transcribe -- python pipeline.py
checkpointkit status --name transcribe
checkpointkit list
checkpointkit resume --name transcribe
```

A completed command is not rerun unless `--force` is supplied. A per-name lease is held for the child process lifetime. Lock wait is configurable:

```bash
checkpointkit run \
  --name transcribe \
  --lock-timeout 30 \
  -- python pipeline.py
```

Snapshot and verify outputs:

```bash
checkpointkit snapshot output/ --manifest artifacts.json
checkpointkit verify artifacts.json
checkpointkit verify artifacts.json --exact --json
```

Normal verification checks recorded files for existence, byte size, and SHA-256 digest. `--exact` also reports files added beneath the original snapshot roots.

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

High-level operations lock, reload, mutate, validate, and atomically install the next generation. Explicit read-modify-write callers can use `load()` and conditional `save()`; a stale generation raises `StateConflictError` rather than replacing newer progress.

## Reproducible crash-and-resume evidence

The repository includes an offline scenario that performs a real child-process termination:

```bash
python examples/crash_resume_demo.py \
  --workspace .checkpointkit-demo \
  --reset
```

It performs an uninterrupted clean run, terminates an equivalent worker after exactly five durable commits, resumes in a new process, verifies committed items were skipped, completes the remaining items, and compares exact SHA-256 manifests.

The report records committed, skipped, resumed, and duplicate counts; generation history; runtimes; evidence paths; and artifact verification. See:

- [`docs/recovery-demo.md`](docs/recovery-demo.md)
- [`docs/recovery-report.schema.json`](docs/recovery-report.schema.json)

CI runs this scenario independently on Linux, Windows, and macOS and uploads each evidence bundle. The package gate depends on all recovery jobs.

## Guarantees and boundaries

CheckpointKit is **workflow/application-level recovery software**. It does not restore process memory or continue at the exact CPU instruction where execution stopped.

Local coordination applies to cooperating CheckpointKit processes on ordinary local filesystems exercised by CI. Advisory locks can be bypassed. NFS, SMB, synchronized folders, object-store mounts, distributed workers, hostile writers, and exactly-once arbitrary external side effects are not claimed.

A command may complete remote work and lose power before terminal local state is written. Use idempotency keys or domain transactions for irreversible external operations.

Read the contracts:

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/failure-model.md`](docs/failure-model.md)
- [`docs/concurrency.md`](docs/concurrency.md)
- [`docs/checkpoint-format.md`](docs/checkpoint-format.md)

## Quality and release evidence

Every release is gated by Ruff and bytecode compilation, branch-aware coverage of at least 90%, Python 3.10–3.14 testing on Linux, current Python testing on Windows and macOS, the three-platform crash-and-resume matrix, package builds, and clean wheel installation.

CodeQL runs independently on pull requests, main-branch pushes, and a weekly schedule. Release assets include SHA-256 checksums and GitHub build provenance attestations.

```bash
gh release verify v0.3.0 -R jerry0327/checkpointkit
gh attestation verify checkpointkit-0.3.0-py3-none-any.whl \
  --repo jerry0327/checkpointkit
```

The release workflow checks out the exact successful `main` commit, refuses to publish if `main` has advanced, and never overwrites an existing tag.

## Project status

CheckpointKit is an early open-source project. It does not claim broad adoption, production deployments, external contributors, or download volume without independent evidence. Reproducible engineering facts and future adoption goals are separated in [`docs/project-evidence.md`](docs/project-evidence.md).

## Contributing and governance

- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`GOVERNANCE.md`](GOVERNANCE.md)
- [`SUPPORT.md`](SUPPORT.md)
- [`SECURITY.md`](SECURITY.md)
- [`ROADMAP.md`](ROADMAP.md)

AI-assisted contributions are reviewed under the same correctness, licensing, security, and testing standards as other contributions.

## License and citation

Apache License 2.0. See [`LICENSE`](LICENSE). Citation metadata is in [`CITATION.cff`](CITATION.cff).
