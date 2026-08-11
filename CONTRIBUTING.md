# Contributing to CheckpointKit

CheckpointKit is intentionally small and correctness-oriented. Contributions are welcome, especially reproducible bug reports, tests for interruption/recovery edge cases, documentation improvements, and narrowly scoped features.

## Before opening a pull request

1. Search existing issues and pull requests.
2. For behavior changes, open or reference an issue that states the recovery problem being solved.
3. Keep unrelated refactors out of the same pull request.
4. Add tests for failure paths, not only happy paths.

## Development setup

```bash
python -m venv .venv
# activate .venv
python -m pip install -e ".[dev]"
ruff check .
pytest
```

## Design principles

- **Recovery semantics must be explicit.** Do not imply exact process continuation when the implementation only restarts work.
- **State must be inspectable.** Prefer documented, versioned formats over opaque blobs.
- **Failure is part of the API.** Tests should exercise interrupted writes, missing artifacts, command failures, and incompatible state.
- **Core stays lightweight.** New runtime dependencies need a concrete justification.
- **Compatibility matters.** Any checkpoint-format change needs a migration or an explicit pre-1.0 breaking-change note.

## Pull requests

Use a focused branch, keep commits understandable, and complete the pull request template. Maintainers may ask for a smaller scope when a change makes recovery behavior harder to reason about.

## Issues and community activity

Please report only real behavior, usage, and adoption. Do not manufacture stars, downloads, contributors, benchmarks, or issue activity. Project metrics should remain auditable.

## Code of conduct

Participation is governed by [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).
