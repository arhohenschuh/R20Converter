"""Regression tests for the Foundry v13 document schema (ADR-002, ADR-005).

Foundry removed every automatic v9 -> v10 document migration in 12.316, so the
converter has to emit the modern field names itself. These tests pin the
renames that are easy to silently revert, and assert that the removed v9 names
are gone rather than merely accompanied by their replacements.
"""

import pytest

from entities.base import Entity
from entities.folders import Folder
from entities.tables import Table

from conftest import FakeDatabase


def makeEntity(cls, tmp_path, arguments=None):
    """Build an entity without running the converter-dependent constructor."""
    obj = cls.__new__(cls)
    obj._database = FakeDatabase(str(tmp_path), arguments)
    obj._converter = None
    return obj


class TestOwnership(object):
    """v10 renamed ``permission`` to ``ownership``; the levels are unchanged."""

    def testLevelsAreStillNumeric(self):
        assert Entity.OWNERSHIP_NONE == 0
        assert Entity.OWNERSHIP_LIMITED == 1
        assert Entity.OWNERSHIP_OBSERVER == 2
        assert Entity.OWNERSHIP_OWNER == 3

    def testOldConstantNamesAreGone(self):
        assert not hasattr(Entity, "PERMISSION_NONE")
        assert not hasattr(Entity, "PERMISSION_OWNER")


class TestFolder(object):
    """v10 renamed ``Folder#parent`` to ``Folder#folder``."""

    def testUsesFolderNotParent(self, tmp_path):
        folder = makeEntity(Folder, tmp_path)
        Folder.__init__(folder, folder._database, "abc", "Monsters", "Actor", None, 1)
        assert "parent" not in folder.entity
        assert "folder" in folder.entity


class TestTableResults(object):
    """v12/v13 reshaped ``TableResult`` -- see ADR-005."""

    def makeTable(self, tmp_path, as_module=False):
        table = makeEntity(Table, tmp_path, {"export_as_module": as_module})
        Table.__init__(table, table._database,
                       {"id": "t1", "name": "Loot", "showplayers": True},
                       0, None)
        return table

    def testResultTypesAreStrings(self):
        assert Table.RESULT_TYPE_TEXT == "text"
        assert Table.RESULT_TYPE_DOCUMENT == "document"

    def testCompendiumResultTypeIsGone(self):
        # v13 merged the "pack" type into "document"; keeping the constant
        # around would invite emitting an invalid value.
        assert not hasattr(Table, "RESULT_TYPE_COMPENDIUM")
        assert not hasattr(Table, "RESULT_TYPE_ENTITY")

    def testTextResult(self, tmp_path):
        table = self.makeTable(tmp_path)
        entry = table.addEntry("A pile of coins")
        assert entry["type"] == "text"
        assert entry["documentUuid"] is None
        assert entry["description"] == "A pile of coins"
        assert "collection" not in entry
        assert "resultId" not in entry
        assert "text" not in entry

    def testWorldDocumentResult(self, tmp_path):
        table = self.makeTable(tmp_path)
        item = makeEntity(Entity, tmp_path)
        item._id = "itemid"
        entry = table.addEntry("Ace", None, 1, item, "Item")
        assert entry["type"] == "document"
        assert entry["documentUuid"] == "Item.itemid"

    def testCompendiumDocumentResult(self, tmp_path):
        table = self.makeTable(tmp_path, as_module=True)
        item = makeEntity(Entity, tmp_path)
        item._id = "itemid"
        entry = table.addEntry("Ace", None, 1, item, "r20-module.cards")
        assert entry["documentUuid"] == "Compendium.r20-module.cards.Item.itemid"

    def testRangesAreContiguous(self, tmp_path):
        table = self.makeTable(tmp_path)
        first = table.addEntry("one", None, 2)
        second = table.addEntry("two", None, 3)
        assert first["range"] == [1, 2]
        assert second["range"] == [3, 5]
        assert table.entity["formula"] == "1d5"


class TestNormalizeSystemData(object):
    """Compendium packs may predate v10 and still use the ``data`` key."""

    def testUpConvertsDataToSystem(self, tmp_path):
        item = makeEntity(Entity, tmp_path)
        item.entity = {"_id": "x", "data": {"hp": 3}}
        Entity.normalizeSystemData(item)
        assert item.entity["system"] == {"hp": 3}
        assert "data" not in item.entity

    def testLeavesModernEntriesAlone(self, tmp_path):
        item = makeEntity(Entity, tmp_path)
        item.entity = {"_id": "x", "system": {"hp": 3}}
        Entity.normalizeSystemData(item)
        assert item.entity["system"] == {"hp": 3}
