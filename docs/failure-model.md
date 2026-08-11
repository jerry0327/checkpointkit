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
- internally inconsistent state.

Readers do not silently reset malformed state, because doing so could repeat expensive or destructive work.

### Process exits without finalization

If a process exits after writing a `running` attempt but before writing its terminal status, the state remains inspectable. The next run or resume changes that attempt to `abandoned`, records when recovery occurred, and creates a new attempt.

This behavior detects stale durable state; it does not prove whether a remote side effect from the abandoned command completed. Workloads that perform external writes should use idempotency keys or their own transactional protocol.

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
- concurrent writers to one local state file;
- transaction isolation on network filesystems;
- recovery from malicious modification by a user who can write the state directory;
- durability after storage-device or filesystem corruption.

These boundaries are part of the API contract. New guarantees require deterministic failure-injection tests before documentation is expanded.
