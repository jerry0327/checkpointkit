# Local concurrency semantics

**Status:** implemented for the 0.2 alpha line

## Guarantee

For checkpoint and run-state documents on tested ordinary local filesystems, cooperating CheckpointKit processes use two layers of coordination:

1. an exclusive advisory operating-system lock on a stable sidecar file;
2. a monotonic durable `generation` checked immediately before atomic replacement.

This prevents cooperating writers from silently losing updates. It also detects a direct, non-cooperating state replacement when that replacement changes the durable generation before the next CheckpointKit commit.

The guarantee is intentionally narrower than “multi-writer transactions everywhere.” All writers must use the same CheckpointKit protocol and lock path, and the filesystem must provide the lock and rename behavior exercised by the project’s Windows, macOS, and Linux CI.

## Lock paths and lifetime

A document such as:

```text
.checkpointkit/transcribe.json
```

uses the sidecar:

```text
.checkpointkit/.transcribe.json.lock
```

The sidecar is a one-byte coordination file and intentionally remains after release. Ownership is attached to the open file descriptor or handle. The operating system releases the lock when the process exits, including an unclean exit; CheckpointKit does not delete a lock merely because a timestamp appears old.

`CheckpointStore` holds the lock only around one read-modify-write transaction. The command runner holds a per-run-name lock for the lifetime of the wrapped subprocess so a second cooperating wrapper cannot start the same recorded command concurrently.

Lock acquisition waits 10 seconds by default. `CheckpointStore(lock_timeout=...)`, `checkpointkit run --lock-timeout`, and `checkpointkit resume --lock-timeout` expose an intentional timeout. Expiry raises `LockTimeoutError`, a subclass of `StateConflictError`, without reading or changing checkpoint contents.

## Generation and compare-and-swap

New item checkpoints and run states carry a non-negative integer `generation`.

- a new logical document begins at generation `0`;
- each successful durable replacement increments it exactly once;
- idempotent high-level operations that do not change state do not write or increment;
- `CheckpointStore.load()` exposes the observed generation;
- `CheckpointStore.save()` requires that generation, explicitly or from the payload;
- a mismatch raises `StateConflictError` before a temporary replacement file is created.

The generation check is performed while the advisory lock is held. A lock without a generation token would serialize cooperating mutations but would not protect a long-lived in-memory snapshot passed later to `save()`. A generation token without a lock would have a time-of-check/time-of-use race. Both mechanisms are required for the tested local contract.

Run-state generation advances once when a `running` attempt is recorded and once when its terminal state is committed. If a hard exit leaves a valid `running` attempt, the next lease holder marks it `abandoned` and appends a new attempt in the next durable generation.

## Backward compatibility

Schema-1 item checkpoint and run-state documents created before 0.2 may omit `generation`. Readers normalize such a document to logical generation `0` in memory but do not rewrite it. The next successful write preserves `schema_version: 1`, adds `generation: 1`, and otherwise follows the current validators.

This is an additive format evolution, not an automatic schema migration.

## Conflict handling

A caller that receives `StateConflictError` must reload current durable state, re-evaluate whether its intended mutation is still valid, and then apply it deliberately. CheckpointKit does not silently retry caller-supplied side effects.

A run-state conflict after the wrapped command has performed external work cannot prove whether that work should be repeated. The run lease prevents a second cooperating wrapper, but exactly-once external behavior still requires application-level idempotency or transactions.

## Unsupported boundaries

CheckpointKit does not currently claim coordination guarantees for:

- NFS, SMB, distributed filesystems, object-store mounts, or synchronized folders;
- processes that bypass the advisory lock or write arbitrary JSON directly;
- hostile writers with permission to replace both state and lock files;
- distributed workers on different hosts without a tested shared-lock protocol;
- exact-once execution of external APIs, databases, or irreversible side effects.

A future backend protocol must define storage-specific conditional writes rather than pretending one local file-lock strategy is universal.

## Test contract

The full CI suite validates:

- two stale snapshots cannot both commit;
- a conflict leaves newer state and temporary-file hygiene intact;
- concurrent cooperating processes merge item progress without lost updates;
- a second run wrapper times out while the run-name lease is held;
- terminating a lock owner does not permanently block later progress;
- a direct generation change is detected before a terminal run-state overwrite;
- legacy missing-generation state is read lazily and upgraded on write;
- the same public behavior runs on supported Linux, Windows, and macOS jobs.
