# Architecture

CheckpointKit is deliberately small: a dependency-free Python runtime core plus explicit JSON formats and command-line tooling.

## Component map

```text
Application or batch worker
        │
        ├── CheckpointStore ── generation CAS ── atomic JSON state
        │                         │
        │                         └── advisory sidecar lock
        │
        ├── command runner ── per-name lease ── attempt history
        │
        └── artifact snapshot / verify ── SHA-256 manifest
```

### Item checkpoint store

`CheckpointStore` records application-defined completion keys. High-level mutations acquire a stable sidecar lock, reload current state, apply one mutation, verify the expected generation, and atomically replace the JSON document.

The public `load()` plus conditional `save()` path supports explicit read-modify-write workflows. A stale generation raises `StateConflictError`; CheckpointKit never silently merges a caller-supplied stale snapshot.

### Command runner

The command wrapper records ordered attempts, process metadata, terminal state, and recovery of attempts left as `running` after an unclean exit. A per-run-name lease is held for the lifetime of the child process, preventing two cooperating wrappers from starting the same named run concurrently.

The runner restarts a recorded command. It does not restore interpreter or operating-system memory.

### Artifact integrity

`snapshot()` records portable relative paths, byte sizes, and SHA-256 digests. `verify()` reports missing, changed, or—under exact verification—unexpected files. Manifest validation rejects traversal, absolute paths, drive prefixes, duplicates, malformed digests, and symlink escapes.

## Durability sequence

A normal checkpoint mutation follows this order:

```text
acquire advisory lock
→ read and validate current state
→ compare durable generation
→ create next-generation payload
→ write temporary file in destination directory
→ flush and fsync file
→ atomic os.replace
→ best-effort parent-directory fsync on POSIX
→ release lock
```

The previous valid document remains in place if serialization or replacement fails. Filesystem and storage-device failures remain outside the guarantees described in [`failure-model.md`](failure-model.md).

## Trust boundaries

The local coordination contract assumes:

- cooperating CheckpointKit processes use the same state and lock paths;
- the underlying ordinary local filesystem provides the lock and rename behavior exercised by CI;
- users with write access to the state directory are trusted;
- workloads define stable completion keys and protect irreversible external side effects separately.

NFS, SMB, synchronized folders, object-store mounts, distributed locks, hostile writers, and exactly-once external transactions are not represented as supported by the local backend.

## Extension direction

A future backend protocol should preserve the same semantic operations—validated reads, conditional generation writes, and explicit conflicts—while replacing local locking with storage-native compare-and-swap or transactions. Remote backends should be added only with deterministic integration tests and documented consistency assumptions.
