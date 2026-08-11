from checkpointkit import CheckpointStore


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
