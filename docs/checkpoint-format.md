# Checkpoint formats

CheckpointKit currently writes three JSON document types. All are pre-1.0 and may evolve.

## Item checkpoint

Created by `CheckpointStore`.

```json
{
  "schema_version": 1,
  "created_at": "...",
  "updated_at": "...",
  "completed": ["item-1"],
  "metadata": {},
  "item_metadata": {
    "item-1": {"rows": 100}
  }
}
```

Completion keys are strings. Applications should choose deterministic keys that remain stable across restarts.

## Command run state

Stored under `.checkpointkit/runs/<name>.json` by default. It records the command, working directory, overall status, and an append-only list of attempts within the current schema.

`resume` reruns the command from its recorded working directory. It does not restore process memory.

## Artifact manifest

Created by `checkpointkit snapshot` and verified by `checkpointkit verify`. Each file records a relative path, byte size, and SHA-256 digest. The manifest stores the relative location of the snapshot base directory so verification can reconstruct paths from the manifest location.
