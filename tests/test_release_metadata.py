from pathlib import Path

import pytest

from tools.release_metadata import (
    ReleaseMetadata,
    ReleaseMetadataError,
    extract_changelog,
    load_release_metadata,
    render_release_notes,
)


def test_repository_release_metadata_is_aligned():
    root = Path(__file__).resolve().parents[1]
    metadata = load_release_metadata(root)

    assert metadata.version == "0.3.0"
    assert metadata.tag == "v0.3.0"
    assert metadata.prerelease is False
    assert "crash-and-resume" in metadata.changelog
    notes = render_release_notes(metadata)
    assert "SHA256SUMS" in notes
    assert "OIDC/Sigstore" in metadata.changelog
    assert "Local-file coordination" in notes


def test_release_metadata_rejects_version_disagreement(tmp_path):
    (tmp_path / "src" / "checkpointkit").mkdir(parents=True)
    (tmp_path / "release").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nversion = "1.2.3"\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "checkpointkit" / "__init__.py").write_text(
        '__version__ = "1.2.4"\n',
        encoding="utf-8",
    )
    (tmp_path / "release" / "intent.txt").write_text("1.2.3\n", encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [1.2.3]\n\n- change\n",
        encoding="utf-8",
    )

    with pytest.raises(ReleaseMetadataError, match="versions disagree"):
        load_release_metadata(tmp_path)


def test_changelog_section_must_exist_and_be_nonempty(tmp_path):
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [2.0.0]\n\n## [1.0.0]\n\n- old\n",
        encoding="utf-8",
    )
    with pytest.raises(ReleaseMetadataError, match="section for 2.0.0 is empty"):
        extract_changelog(tmp_path, "2.0.0")
    with pytest.raises(ReleaseMetadataError, match="no section"):
        extract_changelog(tmp_path, "3.0.0")


def test_render_release_notes_handles_stable_version():
    metadata = ReleaseMetadata(
        version="1.0.0",
        tag="v1.0.0",
        prerelease=False,
        changelog="### Added\n\n- stable",
    )
    notes = render_release_notes(metadata)
    assert notes.startswith("# CheckpointKit v1.0.0")
    assert "- stable" in notes
    assert "Local-file coordination" in notes
