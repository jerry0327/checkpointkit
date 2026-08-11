"""Public exception hierarchy for CheckpointKit."""

from __future__ import annotations


class CheckpointKitError(Exception):
    """Base class for expected CheckpointKit operational errors."""


class StateValidationError(CheckpointKitError):
    """Raised when durable state is malformed or unsupported."""


class StateConflictError(CheckpointKitError):
    """Raised when an operation conflicts with already recorded state."""


class LockTimeoutError(StateConflictError):
    """Raised when a local durable-state lock cannot be acquired in time."""


class UnsafePathError(StateValidationError):
    """Raised when a manifest path is unsafe or escapes its declared base."""
