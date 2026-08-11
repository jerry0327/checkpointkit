# Roadmap

This roadmap describes priorities, not promises or dates. Changes should be driven by demonstrated recovery needs and testable semantics.

## 0.1 — Local recovery primitives

- [x] Atomic JSON checkpoint writes
- [x] Item-level completion tracking
- [x] Command attempt recording
- [x] Restart recorded commands
- [x] SHA-256 artifact snapshot and verification
- [x] CLI and Python package structure
- [x] CI across Python 3.10–3.13
- [ ] Validate behavior on Windows and macOS runners
- [ ] Add corruption/recovery fixtures and format documentation tests

## 0.2 — Safer coordination

- [ ] File-locking strategy for supported local filesystems
- [ ] Compare-and-swap / generation checks to detect stale writers
- [ ] Named batch/run metadata and richer status output
- [ ] Cleanup and retention policies for old attempts
- [ ] Optional JSON Lines event history

## 0.3 — Extensibility

- [ ] Backend protocol for local/object-store implementations
- [ ] S3-compatible reference backend or adapter
- [ ] Pluggable artifact stores
- [ ] Structured hooks for schedulers and agent workflows

## Before 1.0

- Stable checkpoint and manifest schemas
- Documented compatibility / migration policy
- Cross-platform locking semantics
- Failure-injection test suite
- Packaging and signed release process
- Real-world integrations maintained outside the core test fixtures
