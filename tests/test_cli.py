import sys

from checkpointkit.cli import main


def test_cli_run_and_status(tmp_path, capsys):
    state_dir = tmp_path / "state"
    code = main(
        [
            "run",
            "--name",
            "demo",
            "--state-dir",
            str(state_dir),
            "--",
            sys.executable,
            "-c",
            "print('demo')",
        ]
    )
    assert code == 0

    assert main(["status", "--name", "demo", "--state-dir", str(state_dir)]) == 0
    output = capsys.readouterr().out
    assert "status: completed" in output
