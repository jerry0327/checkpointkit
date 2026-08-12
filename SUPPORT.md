# Support

CheckpointKit is maintained on a best-effort open-source basis. There is no guaranteed response time or production support agreement.

## Usage questions

Open a **Usage question** issue and include:

- CheckpointKit and Python versions;
- operating system and filesystem type;
- the smallest reproducible command or code sample;
- sanitized checkpoint, run-state, or manifest structure when relevant;
- expected and observed behavior.

Do not include credentials, patient data, private file contents, access tokens, or other sensitive information.

## Bugs

Use the bug-report form. Recovery and concurrency bugs should include a deterministic reproduction whenever possible. Reports involving network filesystems should identify the exact filesystem and mount behavior because the local locking contract does not assume NFS, SMB, synchronized folders, or object-store mounts.

## Feature requests

Use the feature-request form and explain the recovery problem, required semantics, failure cases, and why the change belongs in a reusable core rather than application code.

## Security reports

Do not open a public issue for a suspected vulnerability. Follow [`SECURITY.md`](SECURITY.md).

## Supported environment

The current release supports Python 3.10 through 3.14. CI exercises Linux across all supported Python versions and the current Python 3.14 runtime on GitHub-hosted Windows and macOS runners.

A platform appearing in CI means the documented test contract passes there; it is not a guarantee for every filesystem, storage device, process supervisor, or external side effect.
