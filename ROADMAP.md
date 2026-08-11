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

## 0.2 — Safer coordination

- [x] Specify local locking and stale-writer detection semantics
- [ ] Add generation / compare-and-swap checks to detect stale writers
- [ ] Add an advisory lock implementation for supported local filesystems
- [ ] Define explicit behavior for unsupported network filesystems
- [ ] Cleanup and retention policies for old attempts
- [ ] Optional JSON Lines event history

## 0.3 — Extensibility and integration

- [ ] Backend protocol for local and object-store implementations
- [ ] S3-compatible reference backend or adapter
- [ ] Pluggable artifact stores
- [ ] Structured hooks for schedulers and agent workflows
- [ ] Real-world reference integrations outside the core unit-test fixtures

## Before 1.0

- Stable checkpoint and manifest schemas
- Documented compatibility and migration policy
- Cross-platform coordination semantics with deterministic tests
- Signed and reproducible release process
- Published package with installation telemetry limited to public package indexes
- Multiple independently maintained integrations or documented external adopters
