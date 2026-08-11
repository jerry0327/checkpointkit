# Changelog

All notable changes to CheckpointKit are documented here. The project follows semantic versioning, including pre-release identifiers while APIs and formats are still evolving.

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
