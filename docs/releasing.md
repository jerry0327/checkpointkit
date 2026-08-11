# Release process

CheckpointKit releases are maintainer actions, not automated consequences of every merge.

## Preconditions

1. `main` CI is green on every supported Python and operating-system job.
2. The changelog has a dated version section.
3. `pyproject.toml` and `checkpointkit.__version__` agree.
4. The wheel and source distribution build in a clean CI job.
5. A wheel-install smoke test runs `checkpointkit --version` and imports the public API.
6. Open security issues that affect the release are resolved or explicitly documented.

## Local verification

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest --cov=checkpointkit --cov-report=term-missing --cov-branch
python -m build
```

## Release intent and automated tagging

A release requires one explicit repository intent file:

```text
release/intent.txt
```

It must contain exactly the same version as `pyproject.toml`, `checkpointkit.__version__`, and a non-empty `CHANGELOG.md` section. After `main` CI succeeds, the `Release` workflow revalidates all four inputs, confirms that the successful commit is still the current `main`, builds the distributions, writes `SHA256SUMS`, and creates the tag and GitHub release.

Pre-release tags use the normalized project version, for example `v0.1.0a1`. The workflow skips an existing tag rather than replacing it. Release notes are generated from the matching changelog section and include the project boundaries. Do not claim adoption, download counts, or platform guarantees that are not supported by public evidence.

## Workflow security boundary

The release workflow runs only after a successful `push` CI event on `main`, checks out that exact commit, and refuses to publish if `main` has advanced. It has `contents: write` permission solely to create the immutable tag and GitHub release. Pull-request CI runs cannot publish.

## Package publishing

PyPI publishing will be enabled only after the package name and trusted-publisher configuration are verified. Long-lived upload tokens should not be committed or stored in project files. Until then, GitHub tags and release artifacts are the authoritative distribution record.
