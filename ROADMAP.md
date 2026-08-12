# Roadmap

This roadmap describes priorities, not promises or dates. Changes should be driven by demonstrated recovery needs and testable semantics.

## 0.1 — Reliable local recovery primitives

- [x] Atomic JSON checkpoint writes
- [x] Item-level completion tracking and rollback
- [x] Command attempt recording and restart
- [x] Stale attempt recovery after an unclean process exit
- [x] SHA-256 artifact snapshot and verification
- [x] Exact verification for unexpected artifacts
- [x] Strict schema and unsafe-path validation
- [x] Stable CLI error handling and JSON output
- [x] CI across Python 3.10–3.14
- [x] Validate core behavior on Linux, Windows, and macOS runners
- [x] Failure-injection fixtures for corruption and interrupted writes
- [x] Package build and wheel-install smoke test

## 0.2 — Safer local coordination

- [x] Specify local locking and stale-writer detection semantics
- [x] Add monotonic generation and compare-and-swap conflict checks
- [x] Add advisory OS locks for supported local filesystems
- [x] Hold a per-name lease across wrapped command execution
- [x] Define and document unsupported network-filesystem behavior
- [x] Test lock timeout, crashed-holder recovery, and concurrent progress on all CI platforms

## 0.3 — Reproducible integration and release evidence

- [x] Real child-process termination and resume reference workload
- [x] Machine-readable recovery report and JSON Schema
- [x] Byte-equivalent clean and recovered artifact verification
- [x] Linux, Windows, and macOS recovery evidence artifacts in CI
- [x] CodeQL analysis
- [x] SHA-256 checksums and GitHub build provenance attestations
- [x] Governance, support, architecture, citation, and claim-boundary documentation

## Next engineering priorities

- [ ] Cleanup and retention policies for old command attempts
- [ ] Optional JSON Lines event history in the core API
- [ ] Backend protocol for local and object-store implementations
- [ ] S3-compatible reference backend or adapter
- [ ] Pluggable artifact stores
- [ ] Structured hooks for schedulers and agent workflows
- [ ] Real integrations maintained outside the core repository

## Before 1.0

- Stable checkpoint and manifest schemas
- Documented compatibility and migration policy
- Cross-platform coordination semantics with deterministic tests
- Reproducible release process with provenance verification
- Published package with installation telemetry limited to public package indexes
- Multiple independently maintained integrations or documented external adopters
