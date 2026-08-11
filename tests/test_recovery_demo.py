from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


def test_real_child_process_termination_and_resume(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "demo"
    report_path = workspace / "report.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(root / "examples" / "crash_resume_demo.py"),
            "--workspace",
            str(workspace),
            "--items",
            "8",
            "--interrupt-after",
            "3",
            "--delay",
            "0.005",
            "--report",
            str(report_path),
            "--reset",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    schema = json.loads(
        (root / "docs" / "recovery-report.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(report)
    assert report["schema_version"] == 1
    assert report["items_completed_before_interruption"] == 3
    assert report["items_skipped_on_resume"] == 3
    assert report["items_processed_after_resume"] == 5
    assert report["duplicate_processing_count"] == 0
    assert report["checkpoint_generation_history"] == list(range(1, 9))
    assert report["runtime"]["python"]
    assert report["runtime"]["platform"]
    assert report["artifact_verification"] == {
        "clean_ok": True,
        "clean_problems": [],
        "equivalent_to_clean_run": True,
        "recovered_ok": True,
        "recovered_problems": [],
    }
