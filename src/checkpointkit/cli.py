"""CheckpointKit command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .artifacts import snapshot, verify
from .errors import CheckpointKitError
from .runner import list_runs, load_run, resume_command, run_command


def _strip_double_dash(command: Sequence[str]) -> list[str]:
    command = list(command)
    if command and command[0] == "--":
        command = command[1:]
    return command


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="checkpointkit",
        description="Durable checkpoint and recovery primitives for long-running jobs.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    run_parser = subparsers.add_parser("run", help="Run a command and record attempt state")
    run_parser.add_argument("--name", required=True, help="Stable name for the recorded run")
    run_parser.add_argument("--state-dir", default=".checkpointkit")
    run_parser.add_argument("--cwd", default=None)
    run_parser.add_argument("--force", action="store_true", help="Rerun even if already completed")
    run_parser.add_argument("command", nargs=argparse.REMAINDER)

    resume_parser = subparsers.add_parser("resume", help="Rerun a previously recorded command")
    resume_parser.add_argument("--name", required=True)
    resume_parser.add_argument("--state-dir", default=".checkpointkit")
    resume_parser.add_argument("--force", action="store_true")

    status_parser = subparsers.add_parser("status", help="Inspect a recorded command run")
    status_parser.add_argument("--name", required=True)
    status_parser.add_argument("--state-dir", default=".checkpointkit")
    status_parser.add_argument("--json", action="store_true", dest="as_json")

    list_parser = subparsers.add_parser("list", help="List recorded command runs")
    list_parser.add_argument("--state-dir", default=".checkpointkit")
    list_parser.add_argument("--json", action="store_true", dest="as_json")

    snapshot_parser = subparsers.add_parser("snapshot", help="Hash files into an artifact manifest")
    snapshot_parser.add_argument("paths", nargs="+")
    snapshot_parser.add_argument("--manifest", default="checkpointkit-artifacts.json")
    snapshot_parser.add_argument(
        "--base-dir",
        default=None,
        help="Base directory used for portable artifact paths (default: current directory)",
    )

    verify_parser = subparsers.add_parser("verify", help="Verify an artifact manifest")
    verify_parser.add_argument("manifest")
    verify_parser.add_argument(
        "--exact",
        action="store_true",
        help="Also reject files added beneath the snapshotted roots",
    )
    verify_parser.add_argument("--json", action="store_true", dest="as_json")

    return parser


def _dispatch(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    if args.subcommand == "run":
        command = _strip_double_dash(args.command)
        if not command:
            parser.error("checkpointkit run requires a command after '--'")
        return run_command(
            args.name,
            command,
            state_dir=args.state_dir,
            cwd=args.cwd,
            force=args.force,
        )

    if args.subcommand == "resume":
        return resume_command(args.name, state_dir=args.state_dir, force=args.force)

    if args.subcommand == "status":
        payload = load_run(args.state_dir, args.name)
        if args.as_json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            attempts = payload["attempts"]
            print(f"name: {payload['name']}")
            print(f"status: {payload['status']}")
            print(f"attempts: {len(attempts)}")
            print(f"command: {' '.join(payload['command'])}")
        return 0

    if args.subcommand == "list":
        runs = list_runs(args.state_dir)
        if args.as_json:
            print(json.dumps(runs, indent=2, sort_keys=True))
        elif not runs:
            print("no recorded runs")
        else:
            for run in runs:
                print(f"{run['name']}\t{run['status']}\t{len(run['attempts'])} attempt(s)")
        return 0

    if args.subcommand == "snapshot":
        payload = snapshot(args.paths, args.manifest, base_dir=args.base_dir)
        print(f"wrote {args.manifest} with {len(payload['files'])} file(s)")
        return 0

    if args.subcommand == "verify":
        problems = verify(args.manifest, exact=args.exact)
        if args.as_json:
            print(json.dumps({"ok": not problems, "problems": problems}, indent=2))
        elif problems:
            for problem in problems:
                print(problem)
        else:
            print(f"verified: {Path(args.manifest)}")
        return 1 if problems else 0

    parser.error("unknown subcommand")
    return 2


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _dispatch(parser, args)
    except KeyboardInterrupt:
        print("checkpointkit: interrupted", file=sys.stderr)
        return 130
    except (CheckpointKitError, OSError) as exc:
        print(f"checkpointkit: error: {exc}", file=sys.stderr)
        return 2
