# Security Policy

Checkpoint files can contain command lines, filesystem paths, workload identifiers, and user-supplied metadata. Treat them as potentially sensitive artifacts.

## Supported versions

CheckpointKit is pre-alpha. Security fixes are applied to the current development line; there is not yet a long-term support branch.

## Reporting a vulnerability

Do **not** publish exploit details in a normal GitHub issue.

Use GitHub's private vulnerability reporting / Security Advisory flow for this repository when it is available. If private reporting is not available, open a minimal public issue asking the maintainer to establish a private contact channel, without including exploit details or sensitive data.

Useful reports include the affected commit/version, threat model, minimal reproduction, and the impact on checkpoint integrity, command execution, path handling, or artifact verification.

## Security boundaries

The local backend is currently designed for a trusted local filesystem and a single writer. It does not claim to protect checkpoint state from a malicious local user with write access, and it does not yet provide multi-process transaction isolation.
