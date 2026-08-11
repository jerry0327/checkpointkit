# Maintainer guide

## Triage

- Ask for a minimal reproduction before diagnosing environment-specific failures.
- Separate checkpoint-integrity bugs from workload-level recovery misunderstandings.
- Treat format corruption, path traversal, unintended command execution, lock bypass, and hash-verification bypasses as security-sensitive until assessed.
- Keep issues open until the live acceptance condition is satisfied; documentation is not a substitute for repository settings or runtime evidence.
- Close duplicates or non-reproducible reports with a short explanation rather than inflating issue counts.

## Pull request review

Review recovery semantics first, code style second. A change that shortens a happy path but makes interrupted state ambiguous should not merge without redesign.

Require deterministic tests for changes to durable formats, locking, attempt recovery, artifact validation, or release automation. Confirm that documentation states what is not guaranteed.

## Release checklist

1. Confirm the version, changelog, and intent metadata agree.
2. Ensure lint, the complete Python test matrix, CodeQL, recovery evidence, coverage, and package gates pass.
3. Confirm the built wheel imports the public API from a clean environment.
4. Review format and compatibility changes.
5. Confirm release assets include wheel, source distribution, and `SHA256SUMS`.
6. Verify the release workflow created provenance attestations.
7. Confirm the tag targets the exact verified `main` commit.
8. Never claim download, contributor, user, or adoption metrics that cannot be independently sourced.

## Maintenance records

Prefer issue → pull request → verified merge → release history over direct pushes. Record failed checks and corrective commits rather than deleting evidence of normal engineering iteration.

## AI assistance

AI assistance may accelerate implementation, triage, tests, documentation, and release work. The maintainer remains responsible for every merged change, including security, licensing, and truthful project claims.
