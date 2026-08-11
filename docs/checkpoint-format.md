# Durable JSON formats

CheckpointKit writes three JSON document types. Readers validate required fields and reject unsupported schema versions instead of guessing. The formats remain pre-1.0 and may evolve with documented changelog entries.

## Validation policy

All documents must be UTF-8 JSON objects. Generated timestamps are timezone-aware ISO 8601 values. Invalid JSON reports its line and column. Unknown schema versions fail closed.

The validator allows unknown top-level fields within a supported schema so operational tools can attach additive metadata, but required fields and invariants remain strict.

## Item checkpoint

Created by `CheckpointStore`:

```json
{
  "schema_version": 1,
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

- completion keys are non-empty, unique strings;
- `metadata` and every `item_metadata` value are JSON objects;
- item metadata may only exist for a completed key;
- applications should choose deterministic keys that remain stable across restarts.

`mark_incomplete()` removes both the completion marker and its item metadata.

## Command run state

Stored under `.checkpointkit/runs/<safe-name>.json` by default. A document records:

- the original run name, command, and absolute working directory;
- overall status;
- creation/update timestamps;
- an ordered, consecutively numbered attempt history.

Attempt statuses are `running`, `completed`, `failed`, `interrupted`, `error`, or `abandoned`. A document may contain at most one `running` attempt, and the top-level status must agree with it. Completed attempts require exit code `0`; failed attempts require a non-zero code.

A hard process exit can leave one valid `running` attempt. On the next run or resume, CheckpointKit preserves it as `abandoned`, records a recovery timestamp and reason, then appends a new attempt. It does not rewrite history to pretend the prior attempt finished normally.

`resume` reruns the command from its recorded working directory. It does not restore process memory.

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
