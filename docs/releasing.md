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

## Tagging

Pre-release tags use the normalized project version:

```text
v0.1.0a1
```

The tag must point to a green commit on `main`. Release notes should summarize user-visible changes, compatibility impact, known limitations, and exact verification commands. Do not claim adoption, download counts, or platform guarantees that are not supported by public evidence.

## Package publishing

PyPI publishing will be enabled only after the package name and trusted-publisher configuration are verified. Long-lived upload tokens should not be committed or stored in project files. Until then, GitHub tags and release artifacts are the authoritative distribution record.
