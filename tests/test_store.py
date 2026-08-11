import json

import pytest

import checkpointkit.store as store_module
from checkpointkit import CheckpointStore, StateValidationError


def test_mark_complete_is_idempotent(tmp_path):
    store = CheckpointStore(tmp_path / "state.json")
    store.mark_complete("a")
    store.mark_complete("a")
    store.mark_complete("b", {"rows": 12})

    assert store.completed_count() == 2
    assert store.is_complete("a")
    assert store.completed_keys() == ("a", "b")
    assert store.load()["item_metadata"]["b"] == {"rows": 12}


def test_set_metadata_persists(tmp_path):
    store = CheckpointStore(tmp_path / "state.json")
    store.set_metadata(model="example", shard=3)

    assert store.load()["metadata"] == {"model": "example", "shard": 3}


def test_mark_incomplete_and_pending_keys(tmp_path):
    store = CheckpointStore(tmp_path / "state.json")
    store.mark_complete("a", {"rows": 2})
    store.mark_complete("b")

    assert store.pending_keys(["a", "c", "c", "d"]) == ("c", "d")
    assert store.mark_incomplete("a") is True
    assert store.mark_incomplete("a") is False
    assert store.pending_keys(["a", "b", "c"]) == ("a", "c")
    assert "a" not in store.load()["item_metadata"]


def test_invalid_json_is_rejected_with_location(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"schema_version": 1,', encoding="utf-8")

    with pytest.raises(StateValidationError, match=r"line 1, column"):
        CheckpointStore(path).load()


def test_unsupported_schema_and_invalid_fields_are_rejected(tmp_path):
    store = CheckpointStore(tmp_path / "state.json")
    payload = store.load()
    payload["schema_version"] = 999
    store.path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(StateValidationError, match="Unsupported checkpoint schema"):
        store.load()

    payload["schema_version"] = 1
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
