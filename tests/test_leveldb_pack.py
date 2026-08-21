"""LevelDB compendium pack tests (ADR-009).

The encoding here was read out of a published module that runs on Foundry
14.365, so these assert against that observed format rather than against what
the writer happens to produce.
"""

import json
import os

import pytest

import leveldb_pack

pytestmark = pytest.mark.skipif(not leveldb_pack.isAvailable(),
                                reason="plyvel is not installed")


def actorDocument(identifier="actor1", items=2):
    return {
        "_id": identifier,
        "name": "Goblin",
        "type": "npc",
        "effects": [],
        "items": [{"_id": "item%d" % n, "name": "Scimitar %d" % n, "type": "weapon",
                   "effects": [{"_id": "eff%d" % n, "name": "Inline effect"}]}
                  for n in range(items)],
        "system": {"details": {"cr": 0.25}},
    }


def sceneDocument(identifier="scene1"):
    return {
        "_id": identifier,
        "name": "Cave",
        "tokens": [{
            "_id": "token1",
            "name": "Goblin",
            "delta": {"system": {"attributes": {"hp": {"value": 5, "max": 7}}}},
        }],
    }


class TestKeyEncoding(object):
    """`!collection!id` and `!collection.embedded!parent.child`."""

    def test_primary_and_embedded_keys(self, tmp_path):
        path = str(tmp_path / "actors")
        leveldb_pack.writePack(path, [actorDocument()], "actors")
        keys = sorted(readKeys(path))
        assert "!actors!actor1" in keys
        assert "!actors.items!actor1.item0" in keys
        assert "!actors.items!actor1.item1" in keys

    def test_values_are_plain_json(self, tmp_path):
        path = str(tmp_path / "actors")
        leveldb_pack.writePack(path, [actorDocument()], "actors")
        raw = readRaw(path, "!actors!actor1")
        assert raw.startswith(b"{")
        assert json.loads(raw.decode("utf-8"))["name"] == "Goblin"

    def test_pack_is_a_directory_with_a_manifest(self, tmp_path):
        path = str(tmp_path / "actors")
        leveldb_pack.writePack(path, [actorDocument()], "actors")
        assert os.path.isdir(path)
        assert "CURRENT" in os.listdir(path)


class TestEmbeddedSplit(object):
    """The parent keeps ids; the children become their own entries."""

    def test_parent_holds_ids_not_objects(self, tmp_path):
        path = str(tmp_path / "actors")
        leveldb_pack.writePack(path, [actorDocument()], "actors")
        parent = json.loads(readRaw(path, "!actors!actor1").decode("utf-8"))
        assert parent["items"] == ["item0", "item1"]

    def test_nested_effect_becomes_its_own_entry(self, tmp_path):
        path = str(tmp_path / "actors")
        leveldb_pack.writePack(path, [actorDocument()], "actors")
        child = json.loads(readRaw(path, "!actors.items!actor1.item0").decode("utf-8"))
        assert child["effects"] == ["eff0"]
        effect = json.loads(
            readRaw(path, "!actors.items.effects!actor1.item0.eff0").decode("utf-8"))
        assert effect["name"] == "Inline effect"

    def test_singleton_delta_uses_token_id_when_missing(self, tmp_path):
        path = str(tmp_path / "scenes")
        leveldb_pack.writePack(path, [sceneDocument()], "scenes")
        token = json.loads(readRaw(path, "!scenes.tokens!scene1.token1").decode("utf-8"))
        assert token["delta"] == "token1"
        delta = json.loads(
            readRaw(path, "!scenes.tokens.delta!scene1.token1.token1").decode("utf-8"))
        assert delta["_id"] == "token1"
        assert delta["system"]["attributes"]["hp"]["value"] == 5

    def test_empty_collection_produces_no_children(self, tmp_path):
        path = str(tmp_path / "actors")
        leveldb_pack.writePack(path, [actorDocument(items=0)], "actors")
        assert not [k for k in readKeys(path) if k.startswith("!actors.items!")]

    def test_split_does_not_mutate_the_caller(self):
        document = actorDocument()
        leveldb_pack.splitDocument(document, "actors")
        assert isinstance(document["items"][0], dict), "caller's document was rewritten"

    def test_every_id_in_the_parent_has_an_entry(self, tmp_path):
        # An id with no matching entry is content that silently disappears.
        path = str(tmp_path / "actors")
        leveldb_pack.writePack(path, [actorDocument(items=5)], "actors")
        keys = set(readKeys(path))
        parent = json.loads(readRaw(path, "!actors!actor1").decode("utf-8"))
        for child_id in parent["items"]:
            assert "!actors.items!actor1.%s" % child_id in keys

    def test_no_entry_is_orphaned(self, tmp_path):
        path = str(tmp_path / "actors")
        leveldb_pack.writePack(path, [actorDocument(items=5)], "actors")
        parent = json.loads(readRaw(path, "!actors!actor1").decode("utf-8"))
        owned = set(parent["items"])
        for key in readKeys(path):
            if key.startswith("!actors.items!"):
                assert key.split(".")[-1] in owned


class TestRoundTrip(object):
    def test_documents_survive_a_write_and_read(self, tmp_path):
        path = str(tmp_path / "actors")
        original = actorDocument(items=3)
        leveldb_pack.writePack(path, [original], "actors")
        restored = leveldb_pack.readPack(path, "actors")
        assert len(restored) == 1
        assert restored[0]["name"] == original["name"]
        assert [i["_id"] for i in restored[0]["items"]] == ["item0", "item1", "item2"]
        assert restored[0]["items"][0]["effects"][0]["_id"] == "eff0"

    def test_singleton_delta_survives_a_write_and_read(self, tmp_path):
        path = str(tmp_path / "scenes")
        original = sceneDocument()
        leveldb_pack.writePack(path, [original], "scenes")
        restored = leveldb_pack.readPack(path, "scenes")
        assert restored[0]["tokens"][0]["delta"]["_id"] == "token1"
        assert restored[0]["tokens"][0]["delta"]["system"] == \
            original["tokens"][0]["delta"]["system"]

    def test_embedded_order_is_the_parents_not_the_key_order(self, tmp_path):
        path = str(tmp_path / "tables")
        table = {"_id": "t1", "name": "Loot",
                 "results": [{"_id": "r%d" % n, "text": str(n)} for n in (9, 1, 5)]}
        leveldb_pack.writePack(path, [table], "tables")
        restored = leveldb_pack.readPack(path, "tables")[0]
        assert [r["_id"] for r in restored["results"]] == ["r9", "r1", "r5"]

    def test_collection_is_detected_when_not_given(self, tmp_path):
        # A system pack is named for its content, not its document type --
        # dnd5e ships "spells24" and "actors24" -- so B031's reader has to work
        # them out from the keys.
        path = str(tmp_path / "spells24")
        leveldb_pack.writePack(path, [actorDocument(items=2)], "actors")
        restored = leveldb_pack.readPack(path)
        assert len(restored) == 1
        assert restored[0]["name"] == "Goblin"
        assert [i["_id"] for i in restored[0]["items"]] == ["item0", "item1"]

    def test_a_parent_that_does_not_list_its_children_is_rejected(self, tmp_path):
        path = str(tmp_path / "actors")
        leveldb_pack.writePack(path, [actorDocument(items=2)], "actors")
        import plyvel
        db = plyvel.DB(path)
        try:
            document = json.loads(db.get(b"!actors!actor1").decode("utf-8"))
            document["items"] = []
            db.put(b"!actors!actor1", json.dumps(document).encode("utf-8"))
        finally:
            db.close()
        with pytest.raises(ValueError, match="orphan ids item0, item1"):
            leveldb_pack.readPack(path)

    def test_permissive_input_reader_recovers_unlisted_children(self, tmp_path):
        path = str(tmp_path / "actors")
        leveldb_pack.writePack(path, [actorDocument(items=2)], "actors")
        import plyvel
        db = plyvel.DB(path)
        try:
            document = json.loads(db.get(b"!actors!actor1").decode("utf-8"))
            document["items"] = []
            db.put(b"!actors!actor1", json.dumps(document).encode("utf-8"))
        finally:
            db.close()
        restored = leveldb_pack.readPack(path, strict=False)[0]
        assert [item["_id"] for item in restored["items"]] == ["item0", "item1"]

    def test_an_embedded_document_without_its_parent_is_rejected(self, tmp_path):
        path = str(tmp_path / "actors")
        leveldb_pack.writePack(path, [actorDocument(items=1)], "actors")
        import plyvel
        db = plyvel.DB(path)
        try:
            db.delete(b"!actors!actor1")
        finally:
            db.close()
        with pytest.raises(ValueError, match="actor1.items has no parent document"):
            leveldb_pack.readPack(path)


class TestFolders(object):
    """A pack carries its own folder tree under ``!folders!`` (ADR-010)."""

    def folder(self, identifier="folder1", parent=None):
        return {"_id": identifier, "name": "Chapter 1", "type": "JournalEntry",
                "folder": parent, "sorting": "m", "sort": 100000}

    def test_folders_are_written_under_their_own_prefix(self, tmp_path):
        path = str(tmp_path / "journal")
        leveldb_pack.writePack(path, [], "journal", folders=[self.folder()])
        assert "!folders!folder1" in readKeys(path)

    def test_folder_values_are_plain_json(self, tmp_path):
        path = str(tmp_path / "journal")
        leveldb_pack.writePack(path, [], "journal", folders=[self.folder()])
        stored = json.loads(readRaw(path, "!folders!folder1").decode("utf-8"))
        assert stored["type"] == "JournalEntry"
        assert stored["sorting"] == "m"

    def test_folders_are_not_read_back_as_documents(self, tmp_path):
        # A folder carries a `name`, so counting it as a document would answer
        # a lookup for the entry of that name.
        path = str(tmp_path / "actors")
        leveldb_pack.writePack(path, [actorDocument()], "actors",
                               folders=[self.folder()])
        restored = leveldb_pack.readPack(path, "actors")
        assert [d["_id"] for d in restored] == ["actor1"]

    def test_rewriting_a_pack_drops_stale_folders(self, tmp_path):
        path = str(tmp_path / "journal")
        leveldb_pack.writePack(path, [], "journal", folders=[self.folder("gone")])
        leveldb_pack.writePack(path, [], "journal", folders=[self.folder("kept")])
        keys = [k for k in readKeys(path) if k.startswith("!folders!")]
        assert keys == ["!folders!kept"]


class TestRewrite(object):
    def test_rewriting_a_pack_drops_the_previous_contents(self, tmp_path):
        # LevelDB merges by default, so a second conversion into the same
        # directory would leave deleted documents behind as orphans.
        path = str(tmp_path / "actors")
        leveldb_pack.writePack(path, [actorDocument("gone")], "actors")
        leveldb_pack.writePack(path, [actorDocument("kept")], "actors")
        identifiers = [d["_id"] for d in leveldb_pack.readPack(path, "actors")]
        assert identifiers == ["kept"]

    def test_a_stale_lock_does_not_block_a_rewrite(self, tmp_path):
        path = str(tmp_path / "actors")
        leveldb_pack.writePack(path, [actorDocument()], "actors")
        open(os.path.join(path, "LOCK"), "wb").close()
        leveldb_pack.writePack(path, [actorDocument()], "actors")


class TestPackMapping(object):
    """The pack list lives in module.py; drift would silently write NeDB."""

    def test_every_module_pack_maps_to_a_collection(self):
        import inspect
        import re
        import module
        source = inspect.getsource(module.Module.__init__)
        names = set(re.findall(r'_newPack\(\s*"([^"]+)"', source))
        assert names, "could not read the pack list out of module.py"
        unmapped = sorted(n for n in names if leveldb_pack.collectionFor(n) is None)
        assert not unmapped, "packs with no LevelDB collection mapping: %s" % unmapped

    def test_collections_that_split_are_known_foundry_ones(self):
        assert set(leveldb_pack.PACK_COLLECTIONS.values()) <= {
            "adventures", "journal", "actors", "items", "scenes", "playlists",
            "tables", "cards", "macros"}


def readKeys(path):
    import plyvel
    db = plyvel.DB(path, create_if_missing=False)
    try:
        return [k.decode("utf-8") for k, _ in db]
    finally:
        db.close()


def readRaw(path, key):
    import plyvel
    db = plyvel.DB(path, create_if_missing=False)
    try:
        return db.get(key.encode("utf-8"))
    finally:
        db.close()
