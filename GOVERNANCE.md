# Governance

CheckpointKit is maintained as a focused open-source project with public technical decisions and explicit release responsibility.

## Roles

### Primary maintainer

`@jerry0327` is the current primary maintainer and is responsible for:

- issue triage and roadmap prioritization;
- reviewing and merging pull requests;
- security-response coordination;
- compatibility and release decisions;
- maintaining CI, release, and repository governance controls.

### Contributors

Anyone may contribute through issues and pull requests. Contributors are expected to follow the code of conduct, document behavioral changes, add deterministic tests, and preserve the project’s stated claim boundaries.

Sustained contributors may be invited to take triage or review responsibility after demonstrating sound technical judgment, constructive participation, and familiarity with the failure model.

## Decision process

Routine changes use public pull-request discussion and maintainer review. Larger changes—durable-format evolution, backend protocols, concurrency semantics, security boundaries, or compatibility policy—should begin with an issue that records:

1. the problem and user impact;
2. proposed semantics and alternatives;
3. failure modes and non-goals;
4. migration or compatibility implications;
5. deterministic acceptance criteria.

The primary maintainer makes the final decision when consensus is incomplete. Decisions should favor a small, testable core over broad claims or unverified abstractions.

## Releases

Releases require:

- aligned package, source, intent, and changelog versions;
- green lint, cross-platform test, recovery, coverage, and package gates;
- a reviewed CodeQL result for the release tree;
- artifacts built from the exact verified `main` commit;
- SHA-256 checksums and build provenance attestations;
- documented limitations and compatibility notes.

The automated release workflow enforces the CI/package conditions and prevents duplicate tags or publication from an outdated `main` commit. CodeQL is reviewed independently before merge because it runs as a separate security workflow.

## Security

Security-sensitive reports follow [`SECURITY.md`](SECURITY.md), not public issue discussion. Supported-branch and disclosure decisions are made by the primary maintainer based on severity and affected releases.

## AI-assisted contributions

AI-assisted code and documentation are welcome, but the submitting human remains accountable for correctness, licensing, tests, security, and review responses. Generated activity, fabricated users, false benchmarks, and synthetic adoption claims are not accepted as project evidence.

## Changes to governance

Material governance changes require a public pull request. The repository history is the authoritative record.
