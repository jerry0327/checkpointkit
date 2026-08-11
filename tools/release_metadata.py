"""Validate release metadata and render deterministic GitHub release notes."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10 CI
    import tomli as tomllib  # type: ignore[no-redef]

_VERSION_ASSIGNMENT = re.compile(r'^__version__\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
_PRERELEASE = re.compile(r"(?:a|b|rc|dev)\d*", re.IGNORECASE)


class ReleaseMetadataError(RuntimeError):
    """Raised when repository release metadata is incomplete or inconsistent."""


@dataclass(frozen=True)
class ReleaseMetadata:
    version: str
    tag: str
    prerelease: bool
    changelog: str


def _read_text(path: Path, *, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReleaseMetadataError(f"Cannot read {label}: {path}") from exc


def read_project_version(root: Path) -> str:
    path = root / "pyproject.toml"
    try:
        payload = tomllib.loads(_read_text(path, label="pyproject"))
        version = payload["project"]["version"]
    except (KeyError, TypeError, tomllib.TOMLDecodeError) as exc:
        raise ReleaseMetadataError("pyproject.toml has no valid project.version") from exc
    if not isinstance(version, str) or not version.strip():
        raise ReleaseMetadataError("pyproject.toml project.version must be a non-empty string")
    return version.strip()


def read_package_version(root: Path) -> str:
    path = root / "src" / "checkpointkit" / "__init__.py"
    match = _VERSION_ASSIGNMENT.search(_read_text(path, label="package version"))
    if match is None:
        raise ReleaseMetadataError("checkpointkit.__version__ assignment was not found")
    return match.group(1)


def read_release_intent(root: Path) -> str:
    intent = _read_text(root / "release" / "intent.txt", label="release intent").strip()
    if not intent or any(character.isspace() for character in intent):
        raise ReleaseMetadataError("release/intent.txt must contain exactly one version")
    return intent


def extract_changelog(root: Path, version: str) -> str:
    lines = _read_text(root / "CHANGELOG.md", label="changelog").splitlines()
    heading = f"## [{version}]"
    start: int | None = None
    for index, line in enumerate(lines):
        if line.startswith(heading):
            start = index + 1
            break
    if start is None:
        raise ReleaseMetadataError(f"CHANGELOG.md has no section for {version}")

    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index].startswith("## ["):
            end = index
            break
    body = "\n".join(lines[start:end]).strip()
    if not body:
        raise ReleaseMetadataError(f"CHANGELOG.md section for {version} is empty")
    return body


def load_release_metadata(root: Path) -> ReleaseMetadata:
    root = root.resolve()
    project_version = read_project_version(root)
    package_version = read_package_version(root)
    intent = read_release_intent(root)
    if len({project_version, package_version, intent}) != 1:
        raise ReleaseMetadataError(
            "Release versions disagree: "
            f"pyproject={project_version!r}, package={package_version!r}, intent={intent!r}"
        )
    return ReleaseMetadata(
        version=project_version,
        tag=f"v{project_version}",
        prerelease=bool(_PRERELEASE.search(project_version)),
        changelog=extract_changelog(root, project_version),
    )


def render_release_notes(metadata: ReleaseMetadata) -> str:
    return (
        f"# CheckpointKit {metadata.tag}\n\n"
        f"{metadata.changelog}\n\n"
        "## Distribution verification\n\n"
        "This release attaches a Python wheel, a source distribution, and `SHA256SUMS`. "
        "It was created only after the corresponding `main` commit passed the repository's "
        "lint, cross-platform test, coverage, and package-install gates.\n\n"
        "CheckpointKit remains application/workflow-level recovery software. The local backend "
        "is single-writer, and durable formats remain pre-1.0.\n"
    )


def _write_github_output(path: Path, metadata: ReleaseMetadata) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"version={metadata.version}\n")
        handle.write(f"tag={metadata.tag}\n")
        handle.write(f"prerelease={'true' if metadata.prerelease else 'false'}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--notes", type=Path, required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    try:
        metadata = load_release_metadata(args.root)
    except ReleaseMetadataError as exc:
        parser.error(str(exc))

    args.notes.write_text(render_release_notes(metadata), encoding="utf-8", newline="\n")
    if args.github_output is not None:
        _write_github_output(args.github_output, metadata)
    print(metadata.version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
