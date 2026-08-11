# Changelog

All notable changes to CheckpointKit are documented here. The project follows semantic versioning. Releases below 1.0 may evolve APIs and durable formats with explicit compatibility notes.

## [0.3.0] - 2026-08-12

### Added

- A deterministic, fully offline crash-and-resume reference workload that terminates a real child process after a controlled number of durable commits.
- A machine-readable recovery report with a committed JSON Schema, runtime metadata, checkpoint generation history, duplicate-processing evidence, elapsed times, and artifact verification results.
- Dedicated Linux, Windows, and macOS recovery CI jobs that upload evidence bundles and block the package gate on failure.
- CodeQL security analysis on pull requests, main-branch pushes, and a weekly schedule.
- GitHub OIDC/Sigstore build provenance attestations for release artifacts and checksums.
- Architecture, recovery-evidence, project-evidence, governance, support, and citation documentation.
- A structured usage-question issue form.

### Changed

- Development status advanced from alpha to beta while remaining explicitly pre-1.0.
- Release verification documentation now covers SHA-256 checksums and GitHub attestations.
- The package gate now depends on the complete test matrix and real recovery evidence from all supported operating systems.
- Source distributions now include governance, support, citation metadata, and JSON documentation schemas.

### Claim boundaries

- This release does not claim broad adoption, package-index downloads, external contributors, production deployments, distributed locking, process-memory restoration, or exactly-once arbitrary external side effects without independent evidence.

## [0.2.0a1] - 2026-08-12

### Added

- Monotonic `generation` tokens for item checkpoint and command run-state documents.
- Conditional `CheckpointStore.save()` semantics that reject stale snapshots with `StateConflictError`.
- Cross-platform advisory sidecar locks for cooperating local writers using only the Python standard library.
- `LockTimeoutError`, exported as a specialized `StateConflictError`.
- Per-run-name leases held for the lifetime of wrapped commands.
- `lock_timeout` API parameters and CLI `--lock-timeout` options for `run` and `resume`.
- A multiprocessing reference example and deterministic lock, crash-release, lost-update, and stale-writer tests.

### Changed

- Legacy schema-1 checkpoint and run-state documents without `generation` are read as generation `0` and upgraded lazily on their next successful write.
- Idempotent item operations no longer perform unnecessary durable replacements or generation increments.
- Human-readable command status now includes the durable generation.
- Local coordination documentation now distinguishes tested cooperating-writer guarantees from unsupported distributed or network-filesystem behavior.

### Fixed

- Prevented cooperating processes from silently overwriting each other’s item progress.
- Prevented a stale in-memory checkpoint payload from replacing a newer durable generation.
- Prevented two cooperating wrappers from launching the same recorded run concurrently.
- Detects a non-cooperating generation change before a terminal run-state overwrite.

## [0.1.0a1] - 2026-08-12

### Added

- Strict validators for checkpoint, run-state, and artifact-manifest JSON documents.
- Public exception hierarchy for operational, validation, conflict, and unsafe-path errors.
- `CheckpointStore.mark_incomplete()` and `CheckpointStore.pending_keys()`.
- Stale run-attempt recovery: unfinished `running` attempts are retained as `abandoned` before resume.
- Attempt audit fields for process ID, hostname, signal termination, and spawn errors.
- `checkpointkit list`, JSON verification output, `snapshot --base-dir`, and `verify --exact`.
- Portable manifest roots for detecting unexpected files.
- Typed-package marker (`py.typed`).
- Linux coverage across Python 3.10–3.14 plus Windows/macOS coverage on Python 3.14.
- Package-build smoke testing, Dependabot configuration, and CODEOWNERS.
- Failure-model, concurrency, and release-process documentation.

### Changed

- Expected CLI failures now produce stable stderr messages without Python tracebacks.
- Artifact verification rejects traversal, absolute paths, Windows drive prefixes, duplicate records, malformed digests, and symlink escapes.
- Atomic JSON writes now perform best-effort parent-directory fsync on POSIX after replacement.
- Development status advanced from pre-alpha to alpha.

## [0.1.0a0] - 2026-08-12

### Added

- Initial `CheckpointStore`, command run/resume tracking, artifact snapshot/verification, CLI, tests, CI, documentation, and Apache-2.0 project governance.
