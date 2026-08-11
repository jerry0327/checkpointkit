# Security Policy

Checkpoint files can contain command lines, filesystem paths, workload identifiers, hostnames, process IDs, error messages, and user-supplied metadata. Treat them as potentially sensitive operational artifacts.

## Supported versions

CheckpointKit is alpha software. Security fixes are applied to the current development line; there is not yet a long-term support branch.

## Reporting a vulnerability

Do **not** publish exploit details in a normal GitHub issue.

Use GitHub private vulnerability reporting / Security Advisories for this repository when available. If private reporting is unavailable, open a minimal public issue asking the maintainer to establish a private contact channel, without exploit details or sensitive data.

Useful reports include the affected commit/version, threat model, minimal reproduction, and impact on checkpoint integrity, command execution, path handling, artifact verification, or state confidentiality.

## Security boundaries

- The local backend assumes a trusted local filesystem and one logical writer per state file.
- Atomic replacement does not protect against a malicious local user who can replace or modify the state directory.
- Artifact manifests are data, not executable instructions. Verification rejects traversal, absolute paths, drive prefixes, duplicate records, malformed hashes, and symlink escapes outside the declared base.
- A manifest controls which files are read for hashing beneath its declared base. Do not verify manifests from an untrusted party against a directory containing sensitive data without reviewing the manifest first.
- Recorded commands may contain secrets passed on the command line. Prefer environment variables or secret-management facilities when the underlying tool supports them.
- CheckpointKit does not provide sandboxing or permission separation for the commands it runs.

See [`docs/failure-model.md`](docs/failure-model.md) and [`docs/concurrency.md`](docs/concurrency.md) for non-security reliability boundaries.
