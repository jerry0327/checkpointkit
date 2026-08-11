# Maintainer guide

## Triage

- Ask for a minimal reproduction before diagnosing environment-specific failures.
- Separate checkpoint-integrity bugs from workload-level recovery misunderstandings.
- Treat format corruption, path traversal, unintended command execution, and hash-verification bypasses as security-sensitive until assessed.
- Close duplicate or non-reproducible issues with a short explanation rather than inflating issue counts.

## Pull request review

Review for recovery semantics first, code style second. A PR that makes a happy path shorter but makes interrupted state ambiguous should not merge without redesign.

## Release checklist

1. Ensure CI passes on the supported Python matrix.
2. Run `python -m build` from a clean checkout.
3. Run tests against the built wheel in a fresh environment.
4. Update `CHANGELOG.md` and version metadata.
5. Confirm public API / checkpoint-format changes are documented.
6. Create a signed or otherwise provenance-backed release when release automation is available.
7. Never claim download/adoption metrics that cannot be sourced from the package registry or GitHub.
