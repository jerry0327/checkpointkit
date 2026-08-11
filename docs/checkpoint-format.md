# Durable JSON formats

CheckpointKit writes three JSON document types. Readers validate required fields and reject unsupported schema versions instead of guessing. The formats remain pre-1.0 and may evolve with documented changelog entries.

## Validation policy

All documents must be UTF-8 JSON objects. Generated timestamps are timezone-aware ISO 8601 values. Invalid JSON reports its line and column. Unknown schema versions fail closed.

The validator allows unknown top-level fields within a supported schema so operational tools can attach additive metadata, but required fields and invariants remain strict.

## Generation compatibility

Item checkpoints and command run states written by the 0.2 alpha line contain a non-negative integer `generation`. Every successful durable replacement increments the generation exactly once.

Older schema-1 item checkpoint and run-state documents may omit the field. They remain readable as logical generation `0`. Reading does not modify the source document; the next successful write adds `generation: 1` while retaining `schema_version: 1`.

Artifact manifests do not use a generation token because they are immutable snapshots rather than read-modify-write state.

## Item checkpoint

Created by `CheckpointStore`:

```json
{
  "schema_version": 1,
  "generation": 3,
  "created_at": "2026-08-12T00:00:00+00:00",
  "updated_at": "2026-08-12T00:00:05+00:00",
  "completed": ["item-1"],
  "metadata": {},
  "item_metadata": {
    "item-1": {"rows": 100}
  }
}
```

Invariants:

- `generation`, when present, is an integer greater than or equal to zero;
- completion keys are non-empty, unique strings;
- `metadata` and every `item_metadata` value are JSON objects;
- item metadata may only exist for a completed key;
- applications should choose deterministic keys that remain stable across restarts.

`mark_incomplete()` removes both the completion marker and its item metadata. Idempotent high-level operations that make no change do not advance generation.

A payload returned by `load()` carries the generation observed by that reader. `save()` performs a conditional write against that token and raises `StateConflictError` if durable state has advanced.

## Command run state

Stored under `.checkpointkit/runs/<safe-name>.json` by default. A document records:

- the original run name, command, and absolute working directory;
- the current durable generation;
- overall status;
- creation/update timestamps;
- an ordered, consecutively numbered attempt history.

A representative terminal document is:

```json
{
  "schema_version": 1,
  "generation": 2,
  "name": "transcribe",
  "command": ["python", "pipeline.py"],
  "cwd": "/work/project",
  "created_at": "2026-08-12T00:00:00+00:00",
  "updated_at": "2026-08-12T00:10:00+00:00",
  "status": "completed",
  "attempts": [
    {
      "number": 1,
      "started_at": "2026-08-12T00:00:00+00:00",
      "finished_at": "2026-08-12T00:10:00+00:00",
      "exit_code": 0,
      "status": "completed",
      "pid": 1234,
      "hostname": "worker-1"
    }
  ]
}
```

Attempt statuses are `running`, `completed`, `failed`, `interrupted`, `error`, or `abandoned`. A document may contain at most one `running` attempt, and the top-level status must agree with it. Completed attempts require exit code `0`; failed attempts require a non-zero code.

A normal command attempt advances generation once when `running` is made durable and once when its terminal result is written. A hard process exit can leave one valid `running` attempt. On the next run or resume, CheckpointKit preserves it as `abandoned`, records a recovery timestamp and reason, then appends a new attempt. It does not rewrite history to pretend the prior attempt finished normally.

`resume` reruns the command from its recorded working directory. It does not restore process memory or guarantee exactly-once external effects.

## Artifact manifest

Created by `checkpointkit snapshot`:

```json
{
  "schema_version": 1,
  "created_at": "2026-08-12T00:00:00+00:00",
  "algorithm": "sha256",
  "base_dir": ".",
  "roots": ["output"],
  "files": [
    {
      "path": "output/result.json",
      "size": 1234,
      "sha256": "...64 lowercase hexadecimal characters..."
    }
  ]
}
```

Paths use `/` separators regardless of host platform. File paths must be relative and may not contain `..`, drive prefixes, backslashes, or absolute roots. Duplicate file or root records are rejected. Resolution through a symlink may not escape the declared base directory.

Normal verification checks recorded files only. Exact verification additionally enumerates `roots` and reports files not present in the manifest. Older schema-1 manifests without `roots` remain valid for normal verification but cannot be used with `--exact`.
