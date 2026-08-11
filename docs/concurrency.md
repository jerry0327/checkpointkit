# Local concurrency decision

**Status:** accepted for the 0.1 line

## Current guarantee

Each checkpoint or run-state file has one logical writer at a time. Atomic replacement prevents a reader from observing a partially written new JSON document, but it does not prevent two writers from reading the same generation and overwriting each other's updates.

CheckpointKit therefore does not advertise multi-writer safety in 0.1.

## Chosen 0.2 design direction

Safer local coordination will combine two mechanisms:

1. **Advisory OS lock** around read-modify-write operations to serialize cooperating processes on supported local filesystems.
2. **Monotonic generation / compare-and-swap check** in durable state so a writer can detect that its read snapshot became stale before replacement.

The generation check remains necessary even with a lock: advisory locks can be bypassed by non-cooperating code and may have inconsistent semantics on some filesystems.

## Lock lifetime and stale recovery

The planned lock will be owned by an open file descriptor or handle and released by the operating system when the process exits. CheckpointKit will not delete a lock merely because a timestamp appears old; time-based lock deletion can break a live slow writer.

Timeouts will surface a conflict error containing the state path and elapsed wait, without exposing checkpoint contents.

## Supported storage boundary

The first locking implementation will target ordinary local filesystems on supported Windows, macOS, and Linux runners. Network filesystems and object-store mounts will be unsupported until their semantics are tested explicitly. The backend protocol planned for 0.3 will allow storage-specific coordination rather than pretending one file-lock strategy is universal.

## Test requirements before implementation is enabled

- two writers cannot both commit from the same generation;
- a crashed lock holder does not permanently block progress;
- timeout behavior is deterministic;
- Windows, macOS, and Linux CI cover the same public semantics;
- unsupported filesystems fail clearly or require explicit opt-in.
