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

## Atomicity

Local JSON state is written to a temporary file in the destination directory, flushed, and moved into place with `os.replace`. This avoids exposing a partially written new JSON document after ordinary process interruption.

Atomic replacement is not the same as transaction isolation. Two processes writing the same checkpoint can still lose updates. Multi-writer behavior will not be advertised until a locking or generation-based protocol is specified and tested on supported platforms.

## Versioning

Every durable format has an integer `schema_version`. Readers reject unsupported versions instead of silently guessing. Before 1.0, format changes may be breaking; they must be noted in the changelog and corresponding documentation.

## Dependency policy

The core currently uses only the Python standard library. Runtime dependencies may be added when they materially improve correctness or portability and cannot reasonably be implemented or isolated behind an optional extra.
