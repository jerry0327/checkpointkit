# Failure model

CheckpointKit is designed around explicit, testable failure behavior. It does not claim that every machine, filesystem, or process termination can be made transactional.

## Covered failures

### Interrupted or failed state writes

State is serialized to a temporary file in the destination directory, flushed, fsynced, and then moved into place with `os.replace`. If serialization or replacement fails:

- the previous valid destination remains unchanged;
- the temporary file is removed;
- the operation raises an error.

After replacement, CheckpointKit attempts to fsync the parent directory on POSIX. Filesystems that do not support directory fsync retain atomic replacement semantics, but power-loss durability depends on the filesystem and operating system.

### Truncated or malformed state

Checkpoint, run-state, and manifest readers reject:

- invalid UTF-8 or JSON;
- non-object roots;
- unsupported schema versions;
- missing or wrongly typed required fields;
- invalid generation values;
- internally inconsistent state.

Readers do not silently reset malformed state, because doing so could repeat expensive or destructive work.

### Concurrent local writers

Cooperating item-checkpoint writers use a stable sidecar OS lock around each read-modify-write operation. A successful durable write increments a monotonic generation. A caller that tries to save a stale payload receives `StateConflictError`; the newer durable state is preserved and no replacement temporary file is created.

A lock wait that exceeds the configured timeout raises `LockTimeoutError`. If a lock owner exits abruptly, the operating system releases the lock; the sidecar file remains and can be reused.

These guarantees apply to the tested local-filesystem protocol. A process that writes state directly without taking the lock can bypass serialization, although a changed generation is detected before the next CheckpointKit replacement.

### Process exits without finalization

The command wrapper holds a per-name lease while its subprocess runs. If the wrapper exits after writing a `running` attempt but before writing its terminal status, the state remains inspectable and the operating system releases the lease. The next run or resume changes that attempt to `abandoned`, records when recovery occurred, and creates a new attempt.

This behavior detects stale durable state; it does not prove whether a remote side effect from the abandoned command completed. Workloads that perform external writes should use idempotency keys or their own transactional protocol.

A wrapped command may also finish its external work and then encounter a generation conflict or power loss before terminal state is durable. CheckpointKit reports the uncertainty rather than silently retrying.

### Artifact drift

Verification distinguishes:

- missing files;
- byte-size mismatches;
- SHA-256 mismatches;
- unexpected files when exact mode is enabled.

Unsafe manifest paths and symlink escapes are validation errors, not ordinary verification problems.

## Deliberate exclusions

CheckpointKit does not currently guarantee:

- process-memory restoration;
- exactly-once execution of arbitrary external side effects;
- coordination with writers that bypass the CheckpointKit lock protocol;
- transaction isolation on NFS, SMB, distributed filesystems, or object-store mounts;
- recovery from malicious modification by a user who can write the state directory;
- durability after storage-device or filesystem corruption.

These boundaries are part of the API contract. New guarantees require deterministic failure-injection tests before documentation is expanded.
