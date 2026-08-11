# Design notes

## Scope

CheckpointKit operates at the **workflow/application layer**. It records durable facts that a workload can use to avoid repeating completed work. It is not an OS-level process image mechanism such as CRIU and does not serialize Python interpreter memory.

## Recovery model

A useful checkpoint should answer three questions:

1. What unit of work was intended?
2. Which units are known to be complete?
3. Which outputs can be verified before work resumes?

The first local primitives therefore separate:

- **item checkpoints** (`CheckpointStore`) for application-defined completion keys;
- **run attempts** for command history and restart behavior;
- **artifact manifests** for content verification.

These are deliberately separate formats so a user can adopt one without accepting hidden coupling to the others.

## Atomicity and local coordination

Local JSON state is written to a temporary file in the destination directory, flushed, and moved into place with `os.replace`. This avoids exposing a partially written new JSON document after ordinary process interruption.

Atomic replacement is not transaction isolation. CheckpointKit therefore combines it with:

- an advisory operating-system lock around cooperating local read-modify-write operations;
- a monotonic `generation` checked immediately before each durable replacement.

The lock closes the normal time-of-check/time-of-use race between cooperating processes. The generation token prevents a stale in-memory snapshot from silently replacing a newer commit and can detect a direct writer that changes generation while a command is running.

These semantics are tested on ordinary local filesystems used by the project’s Linux, Windows, and macOS CI. They are not a distributed lock protocol and are not advertised for network filesystems or object-store mounts.

## Run lease

The command wrapper holds a per-name lock for the lifetime of the subprocess. This prevents a second cooperating wrapper from launching the same recorded command concurrently. A hard wrapper exit releases the OS lock but may leave durable status as `running`; the next lease holder records that attempt as `abandoned` before starting another.

The lease does not prove whether an external side effect completed before a crash. Exactly-once behavior remains the responsibility of the workload through idempotency keys or domain transactions.

## Versioning

Every durable format has an integer `schema_version`. Readers reject unsupported versions instead of silently guessing. The additive schema-1 `generation` field is optional for legacy reads and becomes durable on the next successful write. Before 1.0, format changes may be breaking; they must be noted in the changelog and corresponding documentation.

## Dependency policy

The core currently uses only the Python standard library. Runtime dependencies may be added when they materially improve correctness or portability and cannot reasonably be implemented or isolated behind an optional extra.
