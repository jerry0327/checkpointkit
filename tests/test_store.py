import json
import multiprocessing

import pytest

import checkpointkit.store as store_module
from checkpointkit import CheckpointStore, StateConflictError, StateValidationError


def _mark_items(path, keys):
    store = CheckpointStore(path, lock_timeout=5.0)
    for key in keys:
        store.mark_complete(key, {"writer": key})


def test_mark_complete_is_idempotent_and_generation_tracks_changes(tmp_path):
    store = CheckpointStore(tmp_path / "state.json")
    assert store.load()["generation"] == 0

    store.mark_complete("a")
    assert store.load()["generation"] == 1
    store.mark_complete("a")
    assert store.load()["generation"] == 1
    store.mark_complete("b", {"rows": 12})

    payload = store.load()
    assert payload["generation"] == 2
    assert store.completed_count() == 2
    assert store.is_complete("a")
    assert store.completed_keys() == ("a", "b")
    assert payload["item_metadata"]["b"] == {"rows": 12}


def test_set_metadata_persists_without_incrementing_on_noop(tmp_path):
    store = CheckpointStore(tmp_path / "state.json")
    store.set_metadata(model="example", shard=3)
    first = store.load()
    assert first["metadata"] == {"model": "example", "shard": 3}
    assert first["generation"] == 1

    store.set_metadata(model="example", shard=3)
    assert store.load()["generation"] == 1


def test_mark_incomplete_and_pending_keys(tmp_path):
    store = CheckpointStore(tmp_path / "state.json")
    store.mark_complete("a", {"rows": 2})
    store.mark_complete("b")

    assert store.pending_keys(["a", "c", "c", "d"]) == ("c", "d")
    assert store.mark_incomplete("a") is True
    assert store.mark_incomplete("a") is False
    assert store.pending_keys(["a", "b", "c"]) == ("a", "c")
    assert "a" not in store.load()["item_metadata"]
    assert store.load()["generation"] == 3


def test_two_stale_snapshots_cannot_both_commit(tmp_path):
    store = CheckpointStore(tmp_path / "state.json")
    store.mark_complete("base")
    first = store.load()
    stale = store.load()

    first["metadata"]["winner"] = 1
    saved = store.save(first)
    assert saved["generation"] == 2

    stale["metadata"]["loser"] = 2
    before = store.path.read_text(encoding="utf-8")
    with pytest.raises(StateConflictError, match=r"expected 1, found 2"):
        store.save(stale)

    assert store.path.read_text(encoding="utf-8") == before
    assert list(tmp_path.glob(".state.json.*.tmp")) == []
    assert store.load()["metadata"] == {"winner": 1}


def test_explicit_expected_generation_is_enforced(tmp_path):
    store = CheckpointStore(tmp_path / "state.json")
    payload = store.load()
    payload["metadata"]["value"] = 1
    saved = store.save(payload, expected_generation=0)
    assert saved["generation"] == 1

    with pytest.raises(StateConflictError, match="generation conflict"):
        store.save(saved, expected_generation=0)


def test_legacy_schema_one_without_generation_is_lazy_upgraded(tmp_path):
    store = CheckpointStore(tmp_path / "state.json")
    legacy = store.load()
    legacy.pop("generation")
    original = json.dumps(legacy, sort_keys=True)
    store.path.write_text(original, encoding="utf-8")

    loaded = store.load()
    assert loaded["generation"] == 0
    assert store.path.read_text(encoding="utf-8") == original

    store.set_metadata(upgraded=True)
    upgraded = json.loads(store.path.read_text(encoding="utf-8"))
    assert upgraded["schema_version"] == 1
    assert upgraded["generation"] == 1
    assert upgraded["metadata"] == {"upgraded": True}


def test_cooperating_processes_do_not_lose_item_progress(tmp_path):
    context = multiprocessing.get_context("spawn")
    path = tmp_path / "state.json"
    groups = [["a", "b"], ["c", "d"], ["e", "f"], ["g", "h"]]
    processes = [context.Process(target=_mark_items, args=(path, group)) for group in groups]

    for process in processes:
        process.start()
    for process in processes:
        process.join(10.0)
        if process.is_alive():
            process.terminate()
            process.join(5.0)
        assert process.exitcode == 0

    payload = CheckpointStore(path).load()
    assert set(payload["completed"]) == set("abcdefgh")
    assert payload["generation"] == 8


def test_invalid_json_is_rejected_with_location(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"schema_version": 1,', encoding="utf-8")

    with pytest.raises(StateValidationError, match=r"line 1, column"):
        CheckpointStore(path).load()


def test_unsupported_schema_invalid_generation_and_fields_are_rejected(tmp_path):
    store = CheckpointStore(tmp_path / "state.json")
    payload = store.load()
    payload["schema_version"] = 999
    store.path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(StateValidationError, match="Unsupported checkpoint schema"):
        store.load()

    payload["schema_version"] = 1
    payload["generation"] = True
    store.path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(StateValidationError, match="generation.*integer"):
        store.load()

    payload["generation"] = 0
    payload["completed"] = ["a", "a"]
    store.path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(StateValidationError, match="duplicates"):
        store.load()


def test_orphan_item_metadata_is_rejected(tmp_path):
    store = CheckpointStore(tmp_path / "state.json")
    payload = store.load()
    payload["item_metadata"] = {"not-complete": {"rows": 1}}
    store.path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(StateValidationError, match="not marked complete"):
        store.load()


def test_failed_atomic_replace_preserves_previous_state_and_cleans_temp(tmp_path, monkeypatch):
    store = CheckpointStore(tmp_path / "state.json")
    store.mark_complete("before")
    previous = store.path.read_text(encoding="utf-8")

    def fail_replace(source, destination):
        raise OSError("injected replace failure")

    monkeypatch.setattr(store_module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected"):
        store.mark_complete("after")

    assert store.path.read_text(encoding="utf-8") == previous
    assert list(tmp_path.glob(".state.json.*.tmp")) == []


def test_non_json_serializable_metadata_does_not_corrupt_state(tmp_path):
    store = CheckpointStore(tmp_path / "state.json")
    store.mark_complete("before")
    previous = store.path.read_text(encoding="utf-8")

    with pytest.raises(StateValidationError, match="not JSON serializable"):
        store.set_metadata(bad=object())

    assert store.path.read_text(encoding="utf-8") == previous


def test_item_metadata_must_be_an_object(tmp_path):
    store = CheckpointStore(tmp_path / "state.json")
    with pytest.raises(StateValidationError, match="item metadata must be"):
        store.mark_complete("a", metadata=["not", "an", "object"])  # type: ignore[arg-type]
