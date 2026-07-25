"""Regression tests for the Foundry v13 document schema (ADR-002, ADR-005).

Foundry removed every automatic v9 -> v10 document migration in 12.316, so the
converter has to emit the modern field names itself. These tests pin the
renames that are easy to silently revert, and assert that the removed v9 names
are gone rather than merely accompanied by their replacements.
"""

import pytest

from entities.base import Entity
from entities.folders import Folder
from entities.journal import Handout
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


class TestJournalPages(object):
    """v10 replaced JournalEntry `content`/`img` with a `pages` array."""

    def makeHandout(self, tmp_path, notes="", avatar=""):
        handout = makeEntity(Handout, tmp_path, {"use_original_image_urls": True})
        Handout.__init__(handout, handout._database,
                         {"id": "h1", "name": "Note", "notes": notes,
                          "gmnotes": "", "avatar": avatar,
                          "archived": False, "inplayerjournals": [],
                          "controlledby": []},
                         0, None, "handouts")
        return handout

    def testOldFieldsAreGone(self, tmp_path):
        handout = self.makeHandout(tmp_path, notes="<p>hello</p>")
        assert "content" not in handout.entity
        assert "img" not in handout.entity
        assert "pages" in handout.entity

    def testTextOnlyHandoutHasOneTextPage(self, tmp_path):
        handout = self.makeHandout(tmp_path, notes="<p>hello</p>")
        pages = handout.entity["pages"]
        assert len(pages) == 1
        assert pages[0]["type"] == "text"
        assert pages[0]["text"]["content"] == "<p>hello</p>"
        assert pages[0]["text"]["format"] == Handout.PAGE_FORMAT_HTML
        assert pages[0]["src"] is None

    def testImageOnlyHandoutHasOneImagePage(self, tmp_path):
        handout = self.makeHandout(tmp_path, avatar="http://example.com/a.png")
        pages = handout.entity["pages"]
        assert len(pages) == 1
        assert pages[0]["type"] == "image"
        assert pages[0]["src"] == "http://example.com/a.png"

    def testTextAndImageHandoutHasBothPagesInOrder(self, tmp_path):
        handout = self.makeHandout(tmp_path, notes="<p>hello</p>",
                                   avatar="http://example.com/a.png")
        pages = handout.entity["pages"]
        assert [page["type"] for page in pages] == ["text", "image"]
        assert [page["sort"] for page in pages] == [0, Entity.SORT_ORDER]

    def testEmptyHandoutStillHasAPage(self, tmp_path):
        # An entry with no pages cannot be edited from the Foundry journal UI.
        handout = self.makeHandout(tmp_path)
        assert len(handout.entity["pages"]) == 1

    def testPagesInheritEntryOwnership(self, tmp_path):
        handout = self.makeHandout(tmp_path, notes="<p>hello</p>")
        assert handout.entity["pages"][0]["ownership"]["default"] == -1
        assert Entity.OWNERSHIP_INHERIT == -1

    def testPageIdsAreUnique(self, tmp_path):
        handout = self.makeHandout(tmp_path, notes="<p>hello</p>",
                                   avatar="http://example.com/a.png")
        ids = [page["_id"] for page in handout.entity["pages"]]
        assert len(set(ids)) == len(ids)


class TestDocumentLinks(object):
    """v10 replaced the per-type enrichers (@Actor[], @Compendium[]) with @UUID[]."""

    def testCompendiumUuidIncludesDocumentType(self):
        # v11 added the document type as an explicit UUID segment.
        assert Entity.compendiumUuid("r20-module.actors.abc", "Actor") == \
            "Compendium.r20-module.actors.Actor.abc"

    def makeLinker(self, tmp_path, compendium=False, package="r20-module"):
        # Entity.isCompendiumEntity is derived from the database package, which
        # is None for a world export and set for a module export.
        linker = makeEntity(Entity, tmp_path)
        linker._database._package = package if compendium else None
        return linker

    @pytest.mark.parametrize("kind,document", [
        ("handout", "JournalEntry"),
        ("character", "Actor"),
        ("item", "Item"),
    ])
    def testWorldLink(self, tmp_path, kind, document):
        linker = self.makeLinker(tmp_path)
        html = '<a href="http://journal.roll20.net/%s/-ABC">See this</a>' % kind
        assert linker.replaceEntityLinks(html) == \
            "@UUID[%s.%s]{See this}" % (document, Entity.normalizeID("-ABC"))

    def testCompendiumLink(self, tmp_path):
        linker = self.makeLinker(tmp_path, compendium=True)
        html = '<a href="http://journal.roll20.net/character/-ABC">Bob</a>'
        assert linker.replaceEntityLinks(html) == \
            "@UUID[Compendium.r20-module.actors.Actor.%s]{Bob}" % Entity.normalizeID("-ABC")

    def testLegacySyntaxIsNotEmitted(self, tmp_path):
        linker = self.makeLinker(tmp_path, compendium=True)
        html = '<a href="http://journal.roll20.net/handout/-ABC">Note</a>'
        result = linker.replaceEntityLinks(html)
        assert "@Compendium[" not in result
        assert "@JournalEntry[" not in result

    def testUnknownLinkTypeIsLeftAlone(self, tmp_path):
        linker = self.makeLinker(tmp_path)
        html = '<a href="http://journal.roll20.net/deck/-ABC">Deck</a>'
        assert linker.replaceEntityLinks(html) == html

    def testBracesInLabelAreEscaped(self, tmp_path):
        # Unescaped braces would terminate the @UUID label early.
        linker = self.makeLinker(tmp_path)
        html = '<a href="http://journal.roll20.net/item/-ABC">a{b}c</a>'
        assert linker.replaceEntityLinks(html) == \
            "@UUID[Item.%s]{a_b_c}" % Entity.normalizeID("-ABC")
