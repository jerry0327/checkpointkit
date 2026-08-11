import math
import multiprocessing

import pytest

from checkpointkit import LockTimeoutError
from checkpointkit.locking import FileLock


def _hold_lock(path, ready, release):
    with FileLock(path, timeout=5.0):
        ready.set()
        release.wait(10.0)


def test_second_process_times_out_then_acquires_after_release(tmp_path):
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    release = context.Event()
    lock_path = tmp_path / "state.lock"
    process = context.Process(target=_hold_lock, args=(lock_path, ready, release))
    process.start()
    assert ready.wait(5.0)

    try:
        with pytest.raises(LockTimeoutError, match="Timed out"):
            with FileLock(lock_path, timeout=0.1, poll_interval=0.01):
                raise AssertionError("contended lock must not be acquired")
    finally:
        release.set()
        process.join(5.0)
        if process.is_alive():
            process.terminate()
            process.join(5.0)

    assert process.exitcode == 0
    with FileLock(lock_path, timeout=1.0):
        assert lock_path.exists()


def test_operating_system_releases_lock_when_holder_is_terminated(tmp_path):
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    release = context.Event()
    lock_path = tmp_path / "crash.lock"
    process = context.Process(target=_hold_lock, args=(lock_path, ready, release))
    process.start()
    assert ready.wait(5.0)

    process.terminate()
    process.join(5.0)
    assert not process.is_alive()

    with FileLock(lock_path, timeout=1.0):
        assert lock_path.exists()


def test_lock_configuration_rejects_invalid_numbers(tmp_path):
    for timeout in (-1, math.inf, math.nan):
        with pytest.raises(ValueError, match="timeout"):
            FileLock(tmp_path / "state.lock", timeout=timeout)
    for interval in (0, -1, math.inf, math.nan):
        with pytest.raises(ValueError, match="poll interval"):
            FileLock(tmp_path / "state.lock", poll_interval=interval)
