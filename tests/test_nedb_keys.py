import json

import pytest

from conftest import FakeDatabase
from entities.base import Entity


def make_entity(tmp_path, export_as_module=False):
    entity = Entity.__new__(Entity)
    entity._database = FakeDatabase(
        str(tmp_path), {"export_as_module": export_as_module})
    entity._converter = None
    return entity


def test_world_serialization_normalizes_nested_nedb_keys(tmp_path):
    entity = make_entity(tmp_path)
    entity.entity = {
        "_id": "test",
        "flags": {
            "beyond5e-2014-compendium": {
                "beyond5e-2.5.0": {"$source.version": "2.5.0"}
            }
        },
    }

    serialized = json.loads(str(entity))

    assert serialized["flags"]["beyond5e-2014-compendium"] == {
        "beyond5e-2_5_0": {"_source_version": "2.5.0"}
    }
    assert "beyond5e-2.5.0" in entity.entity["flags"]["beyond5e-2014-compendium"]


def test_world_serialization_rejects_normalized_key_collision(tmp_path):
    entity = make_entity(tmp_path)
    entity.entity = {"flags": {"version.1": {}, "version_1": {}}}

    with pytest.raises(ValueError, match="NeDB key collision"):
        str(entity)


def test_module_serialization_preserves_leveldb_keys(tmp_path):
    entity = make_entity(tmp_path, export_as_module=True)
    entity.entity = {"flags": {"fixup": {"beyond5e-1.1.07": True}}}

    serialized = json.loads(str(entity))

    assert serialized["flags"]["fixup"] == {"beyond5e-1.1.07": True}
