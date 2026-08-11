# Release process

CheckpointKit releases are explicit maintainer actions, not automatic consequences of every merge.

## Preconditions

1. `main` CI is green on every supported Python and operating-system job.
2. Linux, Windows, and macOS crash-and-resume evidence jobs pass.
3. The changelog has a dated version section.
4. `pyproject.toml`, `checkpointkit.__version__`, and `release/intent.txt` agree.
5. The wheel and source distribution build in a clean CI job.
6. A wheel-install smoke test runs `checkpointkit --version` and imports the public API.
7. Open security issues affecting the release are resolved or explicitly documented.

## Local verification

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest --cov=checkpointkit --cov-report=term-missing --cov-branch
python examples/crash_resume_demo.py --workspace .checkpointkit-demo --reset
python -m build
```

## Release intent and automated tagging

A release requires one explicit repository intent file:

```text
release/intent.txt
```

It must contain exactly the same version as `pyproject.toml`, `checkpointkit.__version__`, and a non-empty `CHANGELOG.md` section.

After `main` CI succeeds, the `Release` workflow:

1. checks out the exact successful commit;
2. revalidates release metadata;
3. confirms that commit is still the current `main`;
4. refuses to replace an existing tag;
5. builds the wheel and source distribution;
6. writes `SHA256SUMS`;
7. creates GitHub OIDC/Sigstore provenance attestations;
8. creates the tag and GitHub release with all distribution files.

Pre-release tags use normalized project versions such as `v0.2.0a1`. A version without a pre-release identifier, such as `v0.3.0`, is published as a normal GitHub release. Release notes are generated from the matching changelog section and include the project boundaries.

## Workflow security boundary

The release workflow runs only after a successful `push` CI event on `main`, checks out that exact commit, and refuses to publish if `main` has advanced. Pull-request CI cannot publish. The workflow receives only the permissions required to create release contents and OIDC-backed attestations.

## Verify a release

After downloading a wheel or source distribution:

```bash
sha256sum -c SHA256SUMS
gh release verify v0.3.0 -R jerry0327/checkpointkit
gh attestation verify checkpointkit-0.3.0-py3-none-any.whl \
  --repo jerry0327/checkpointkit
```

For stricter policies, verify the signer workflow identity with the GitHub CLI’s attestation options.

## Package publishing

PyPI publishing will be enabled only after the package name and trusted-publisher configuration are verified. Long-lived upload tokens must not be committed or stored in project files. Until then, GitHub tags, release assets, checksums, and attestations are the authoritative distribution record.

Do not claim adoption, download counts, or platform guarantees that are not supported by independent public evidence.
