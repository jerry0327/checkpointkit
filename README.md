# CheckpointKit

[![CI](https://github.com/jerry0327/checkpointkit/actions/workflows/ci.yml/badge.svg)](https://github.com/jerry0327/checkpointkit/actions/workflows/ci.yml)
[![CodeQL](https://github.com/jerry0327/checkpointkit/actions/workflows/codeql.yml/badge.svg)](https://github.com/jerry0327/checkpointkit/actions/workflows/codeql.yml)

**Crash-resilient, local-first checkpointing and resume primitives for long-running AI, data, and batch jobs.**

CheckpointKit gives Python workloads an explicit recovery layer without requiring a distributed scheduler. It records durable item progress, command-attempt history, and artifact integrity so an interrupted process can be inspected and restarted without blindly repeating all completed work.

Typical workloads include transcription, OCR, model evaluation, dataset conversion, scraping, media processing, local agent pipelines, and other jobs that may run for minutes or hours.

> **Current release: `0.3.0` (beta).** The implementation and documented local recovery contract are tested across Linux, Windows, and macOS. The public API and durable formats remain pre-1.0 and may evolve with documented migration notes.

## Why it exists

Long-running jobs fail for routine reasons: a notebook disconnects, a runner is reclaimed, a process crashes, a machine reboots, or one input is malformed. Without inspectable durable state, recovery becomes guesswork and expensive work gets repeated.

CheckpointKit provides a small, dependency-free runtime core:

- atomic, validated JSON checkpoint state;
- item-level completion tracking and rollback;
- monotonic generations with stale-writer detection;
- cross-platform advisory locks for cooperating local writers;
- per-run-name leases and ordered command attempt history;
- stale-attempt recovery after unclean process exit;
- artifact snapshots with SHA-256 and exact verification;
- stable CLI errors and machine-readable output;
- typed Python APIs.

The recovery cycle is explicit:

```text
run → checkpoint → interruption → inspect → resume → verify
```

## Install

Install the verified release wheel directly from GitHub:

```bash
python -m pip install \
  https://github.com/jerry0327/checkpointkit/releases/download/v0.3.0/checkpointkit-0.3.0-py3-none-any.whl
```

Or install a tagged source checkout:

```bash
python -m pip install \
  "checkpointkit @ git+https://github.com/jerry0327/checkpointkit.git@v0.3.0"
```

For development:

```bash
git clone https://github.com/jerry0327/checkpointkit.git
cd checkpointkit
python -m venv .venv
# Activate .venv for your shell, then:
python -m pip install -e ".[dev]"
```

Python 3.10 through 3.14 is supported.

## CLI

Wrap a command and keep durable attempt metadata:

```bash
checkpointkit run --name transcribe -- python pipeline.py
checkpointkit status --name transcribe
checkpointkit list
checkpointkit resume --name transcribe
```

A completed command is not rerun unless `--force` is supplied. A per-name lease is held for the child process lifetime. Set the lock wait explicitly when needed:

```bash
checkpointkit run \
  --name transcribe \
  --lock-timeout 30 \
  -- python pipeline.py
```

Snapshot output artifacts and verify them later:

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

High-level operations acquire the sidecar lock, reload current state, apply one mutation, and atomically install the next generation.

For an explicit read-modify-write operation:

```python
from checkpointkit import StateConflictError

payload = store.load()
payload["metadata"]["model"] = "example-v2"

try:
    saved = store.save(payload)
    print(saved["generation"])
except StateConflictError:
    # Another writer committed first. Reload and deliberately re-evaluate the mutation.
    raise
```

A stale snapshot never silently replaces a newer durable generation.

## Real crash-and-resume evidence

The repository includes an offline integration scenario that performs a real child-process termination:

```bash
python examples/crash_resume_demo.py \
  --workspace .checkpointkit-demo \
  --reset
```

It performs an uninterrupted clean run, terminates an equivalent worker after exactly five durable commits, resumes with a new process, verifies that committed items were skipped, completes the remaining items, and compares exact SHA-256 manifests.

The machine-readable report includes committed, skipped, resumed, and duplicate counts; generation history; runtime details; elapsed times; and supporting evidence paths. See:

- [`docs/recovery-demo.md`](docs/recovery-demo.md)
- [`docs/recovery-report.schema.json`](docs/recovery-report.schema.json)

CI runs this scenario independently on Linux, Windows, and macOS and uploads each evidence bundle. The package gate depends on all recovery jobs.

## Guarantees and boundaries

CheckpointKit is **workflow/application-level recovery software**. It does not freeze arbitrary process memory or continue at the exact CPU instruction where execution stopped.

The local coordination guarantee applies to cooperating CheckpointKit processes on ordinary local filesystems exercised by CI. Advisory locks can be bypassed. NFS, SMB, synchronized folders, object-store mounts, distributed workers, hostile writers, and exactly-once arbitrary external side effects are not claimed.

A command may complete remote work and lose power before its terminal local state is written. Use idempotency keys or domain transactions for irreversible external operations.

Read the full contracts before relying on the toolkit:

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/failure-model.md`](docs/failure-model.md)
- [`docs/concurrency.md`](docs/concurrency.md)
- [`docs/checkpoint-format.md`](docs/checkpoint-format.md)

## Quality and release evidence

Every release is gated by:

- Ruff and bytecode compilation;
- branch-aware coverage of at least 90%;
- Python 3.10–3.14 testing on Linux;
- current Python testing on Windows and macOS;
- the real crash-and-resume matrix;
- wheel and source-distribution builds;
- clean wheel installation and public API smoke tests;
- CodeQL analysis;
- SHA-256 checksums and GitHub build provenance attestations.

Verify a downloaded release with a current GitHub CLI:

```bash
gh release verify v0.3.0 -R jerry0327/checkpointkit
gh attestation verify checkpointkit-0.3.0-py3-none-any.whl \
  --repo jerry0327/checkpointkit
```

The release workflow checks out the exact successful `main` commit, refuses to publish if `main` has advanced, and never overwrites an existing tag.

## Project status

CheckpointKit is an early open-source project. It does not claim broad adoption, production deployments, external contributors, or download volume without independent evidence. The repository’s verifiable engineering and maintenance evidence—and the boundary between current facts and future adoption goals—is summarized in [`docs/project-evidence.md`](docs/project-evidence.md).

## Contributing and governance

Bug reports, focused proposals, documentation improvements, tests, and pull requests are welcome.

- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`GOVERNANCE.md`](GOVERNANCE.md)
- [`SUPPORT.md`](SUPPORT.md)
- [`SECURITY.md`](SECURITY.md)
- [`ROADMAP.md`](ROADMAP.md)

AI-assisted contributions are reviewed under the same correctness, licensing, security, and testing standards as other contributions.

## License and citation

Apache License 2.0. See [`LICENSE`](LICENSE).

Citation metadata is available in [`CITATION.cff`](CITATION.cff).
