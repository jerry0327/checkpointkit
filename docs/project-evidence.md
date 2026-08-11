# Project evidence and claim boundaries

This document separates facts that are reproducible from repository history from claims that the project does not yet make.

## Reproducible engineering evidence

CheckpointKit provides:

- typed Python APIs and a CLI for item checkpoints, command attempts, resume, and artifact verification;
- atomic JSON replacement, strict durable-state validation, generation-based conflict detection, and cross-platform advisory locking;
- deterministic failure-injection and multiprocessing tests;
- a real child-process crash-and-resume scenario on Linux, Windows, and macOS CI;
- a branch-aware coverage gate of at least 90%;
- wheel and source-distribution installation tests;
- CodeQL analysis;
- automated releases with SHA-256 checksums and GitHub artifact provenance attestations;
- public issue, pull-request, changelog, security, governance, and release-management records.

The crash-and-resume scenario and report format are documented in [`recovery-demo.md`](recovery-demo.md).

## Maintainer evidence

Repository history records the normal maintenance cycle rather than manufactured activity:

```text
problem statement
→ issue with acceptance criteria
→ implementation branch
→ pull request
→ CI failure or review feedback when present
→ corrective commit
→ green cross-platform gates
→ squash merge
→ main-branch verification
→ release
```

Issues are kept open when the live condition is not satisfied. For example, documentation cannot substitute for an actually enforced repository ruleset.

## Adoption status

CheckpointKit is an early project. This repository does not claim broad adoption, production deployments, external contributors, package-index downloads, or ecosystem criticality without independent evidence. Stars, forks, downloads, and users must arise from genuine use; they are not generated or inferred from CI activity.

The present ecosystem case is prospective but concrete: long-running AI, data, media, evaluation, transcription, OCR, and batch workloads frequently need inspectable progress recovery without adopting a full distributed scheduler. CheckpointKit is intended to provide a narrow, reusable local primitive for that gap.

## Evidence expected next

The next meaningful signals are:

- independent users reproducing the recovery demo;
- bug reports based on real workloads;
- documented integrations maintained outside this repository;
- package-index publication and verifiable install activity;
- external pull requests and review history.

These are adoption goals, not current claims.
