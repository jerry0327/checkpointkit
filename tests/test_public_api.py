import checkpointkit


def test_public_version_and_exceptions_are_exported():
    assert checkpointkit.__version__ == "0.1.0a1"
    assert issubclass(checkpointkit.StateValidationError, checkpointkit.CheckpointKitError)
