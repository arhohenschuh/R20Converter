"""Folder hierarchy tests (ADR-010, ADR-011).

Module exports used to clear every ``folder`` field and never build a tree at
all, so a converted adventure imported as one flat list per pack. These pin the
tree, its order, and the manifest that supplies the one hierarchy Roll20 does
not export -- scene chapters.
"""

import json

import pytest

import leveldb_pack
from entities.base import Entity
from entities.folders import Folder, Folders
from entities.journal import Handout

from conftest import FakeDatabase


class FakeConverter(object):
    """Just enough converter for :class:`Folders` and the entities it feeds."""

    def __init__(self, tmp_path, campaign, **arguments):
        self.path = str(tmp_path)
        self.name = "my-module"
        self.campaign = campaign
        self._arguments = arguments
        self.folders = None
        self.messages = []

    def getArgument(self, name, default=None):
        return self._arguments.get(name, default)

    def logInfo(self, msg):
        self.messages.append(msg)

    logWarning = logInfo
    logError = logInfo


def makeCampaign(journalfolder=(), pages=(), handouts=(), characters=()):
    return {
        "journalfolder": list(journalfolder),
        "pages": list(pages),
        "handouts": list(handouts),
        "characters": list(characters),
        "players": [],
        "jukebox": [],
        "pdfs": [],
        "tables": [],
        "decks": [],
    }


def makePage(identifier, name, archived=False, placement=0):
    return {"id": identifier, "name": name, "archived": archived,
            "placement": placement}


def makeFolders(tmp_path, campaign, **arguments):
    converter = FakeConverter(tmp_path, campaign, **arguments)
    folders = Folders(converter)
    converter.folders = folders
    return folders


def writeManifest(tmp_path, manifest):
    path = tmp_path / "scene-folders.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return str(path)


class TestFolderDocument(object):
    def testSortingIsManual(self, tmp_path):
        # Foundry defaults Folder#sorting to "a", which would re-order a
        # correctly restored tree alphabetically.
        folder = Folder(FakeDatabase(str(tmp_path)), "f1", "Part 3", "JournalEntry", None, 0)
        assert folder.entity["sorting"] == "m"

    def testSiblingsDoNotShareASortValue(self, tmp_path):
        database = FakeDatabase(str(tmp_path))
        first = Folder(database, "sib-a", "First", "JournalEntry", None, 0)
        second = Folder(database, "sib-b", "Second", "JournalEntry", None, 1)
        assert first.entity["sort"] != second.entity["sort"]
        assert first.entity["sort"] < second.entity["sort"]


class TestJournalHierarchy(object):
    """The Roll20 ``journalfolder`` tree survives a module export."""

    def campaign(self):
        return makeCampaign(
            journalfolder=[{"id": "f1", "n": "Chapter 1", "i": ["h1"]}],
            handouts=[{"id": "h1", "name": "Rumours", "archived": False}])

    def testFolderIsBuiltForAModuleExport(self, tmp_path):
        folders = makeFolders(tmp_path, self.campaign(), export_as_module=True)
        journal = folders.forType("JournalEntry")
        assert [folder["name"] for folder in journal] == ["Chapter 1"]

    def testForTypeScopesTheTreeToOnePack(self, tmp_path):
        folders = makeFolders(tmp_path, self.campaign(), export_as_module=True)
        assert folders.forType("Actor") == []
        assert folders.forType("Scene") == []

    def testHandoutKeepsItsFolderInAModuleExport(self, tmp_path):
        database = FakeDatabase(str(tmp_path), {"export_as_module": True})
        handout = Handout.__new__(Handout)
        Handout.__init__(handout, database,
                         {"id": "h1", "name": "Rumours", "notes": "", "gmnotes": "",
                          "avatar": "", "archived": False},
                         0, "handout-f1", "journal")
        assert handout.entity["folder"] == Entity.normalizeID("handout-f1")


class TestSceneFolderManifest(object):
    def campaign(self):
        return makeCampaign(pages=[makePage("p1", "Upper Works"),
                                   makePage("p2", "The Dungeons"),
                                   makePage("p3", "Start")])

    def manifest(self, **overrides):
        manifest = {
            "schema": Folders.SCENE_FOLDER_SCHEMA,
            "root": "Against the Giants - Scenes",
            "folders": [{"name": "Steading of the Hill Giant Chief",
                         "scenes": ["Upper Works", "The Dungeons"]}],
            "rootScenes": ["Start"],
        }
        manifest.update(overrides)
        return manifest

    def testNoManifestCreatesNoSceneFolders(self, tmp_path):
        folders = makeFolders(tmp_path, self.campaign(), export_as_module=True)
        assert folders.forType("Scene") == []

    def testRootAndChapterFoldersAreCreated(self, tmp_path):
        path = writeManifest(tmp_path, self.manifest())
        folders = makeFolders(tmp_path, self.campaign(), export_as_module=True,
                              scene_folders=path)
        scenes = folders.forType("Scene")
        assert [folder["name"] for folder in scenes] == [
            "Against the Giants - Scenes", "Steading of the Hill Giant Chief"]
        root, chapter = scenes
        assert root["folder"] is None
        assert chapter["folder"] == root["_id"]
        assert all(folder["sorting"] == "m" for folder in scenes)

    def testScenesAreAssignedInDeclaredOrder(self, tmp_path):
        path = writeManifest(tmp_path, self.manifest())
        folders = makeFolders(tmp_path, self.campaign(), export_as_module=True,
                              scene_folders=path)
        chapter = "scene-folder-Steading of the Hill Giant Chief"
        assert folders.sceneAssignment("p1") == (chapter, Entity.SORT_ORDER)
        assert folders.sceneAssignment("p2") == (chapter, 2 * Entity.SORT_ORDER)

    def testRootScenesSitBesideTheChapterFolders(self, tmp_path):
        path = writeManifest(tmp_path, self.manifest())
        folders = makeFolders(tmp_path, self.campaign(), export_as_module=True,
                              scene_folders=path)
        (folder_id, _sort) = folders.sceneAssignment("p3")
        assert folder_id == "scene-folder-root"

    def testUndeclaredPagesAreLeftAtTheRoot(self, tmp_path):
        campaign = self.campaign()
        campaign["pages"].append(makePage("p4", "Bonus Map"))
        path = writeManifest(tmp_path, self.manifest())
        folders = makeFolders(tmp_path, campaign, export_as_module=True,
                              scene_folders=path)
        assert folders.sceneAssignment("p4") is None

    def testAPageMayBeReferencedByID(self, tmp_path):
        manifest = self.manifest(folders=[{"name": "Chapter", "scenes": [{"id": "p2"}]}],
                                 rootScenes=[])
        path = writeManifest(tmp_path, manifest)
        folders = makeFolders(tmp_path, self.campaign(), export_as_module=True,
                              scene_folders=path)
        assert folders.sceneAssignment("p2") == ("scene-folder-Chapter", Entity.SORT_ORDER)

    def testAnUnknownSceneAborts(self, tmp_path):
        manifest = self.manifest(folders=[{"name": "Chapter", "scenes": ["Nowhere"]}],
                                 rootScenes=[])
        path = writeManifest(tmp_path, manifest)
        with pytest.raises(ValueError, match="matches 0 pages"):
            makeFolders(tmp_path, self.campaign(), export_as_module=True,
                        scene_folders=path)

    def testAnAmbiguousSceneNameAborts(self, tmp_path):
        campaign = self.campaign()
        campaign["pages"].append(makePage("p9", "Upper Works"))
        path = writeManifest(tmp_path, self.manifest())
        with pytest.raises(ValueError, match="matches 2 pages"):
            makeFolders(tmp_path, campaign, export_as_module=True, scene_folders=path)

    def testDeclaringAPageTwiceAborts(self, tmp_path):
        manifest = self.manifest(
            folders=[{"name": "A", "scenes": ["Start"]}], rootScenes=["Start"])
        path = writeManifest(tmp_path, manifest)
        with pytest.raises(ValueError, match="more than once"):
            makeFolders(tmp_path, self.campaign(), export_as_module=True,
                        scene_folders=path)

    def testAForeignSchemaIsRejected(self, tmp_path):
        # The pipeline's own post-conversion manifest addresses Foundry ids,
        # which do not exist yet at conversion time (ADR-011).
        path = writeManifest(tmp_path, self.manifest(schema="r20-scene-folders/v1"))
        with pytest.raises(ValueError, match="needs schema"):
            makeFolders(tmp_path, self.campaign(), export_as_module=True,
                        scene_folders=path)


class TestPackFolderTypes(object):
    def testEveryPackDeclaresAFolderType(self):
        # A pack without one silently ships flat, which is the defect ADR-010
        # exists to remove.
        assert set(leveldb_pack.PACK_FOLDER_TYPES) == set(leveldb_pack.PACK_COLLECTIONS)

    def testUnknownPackHasNoFolderType(self):
        assert leveldb_pack.folderTypeFor("spells24") is None


class FakeBatch(object):
    def __init__(self, puts):
        self._puts = puts

    def __enter__(self):
        return self

    def __exit__(self, *exception):
        return False

    def put(self, key, value):
        self._puts.append((key.decode("utf-8"), json.loads(value.decode("utf-8"))))


class FakePlyvel(object):
    """Records what would be stored, so the key layout is testable anywhere.

    ``plyvel`` is a native extension with no wheel for every interpreter, which
    skips the whole of ``test_leveldb_pack.py`` on those machines -- including
    the assertions that folders reach the pack at all.
    """

    def __init__(self):
        self.puts = []

    def DB(self, path, create_if_missing=False):
        return self

    def write_batch(self):
        return FakeBatch(self.puts)

    def close(self):
        pass


class TestFolderWriting(object):
    def write(self, monkeypatch, tmp_path, folders):
        fake = FakePlyvel()
        monkeypatch.setattr(leveldb_pack, "plyvel", fake)
        leveldb_pack.writePack(str(tmp_path / "journal"), [], "journal", folders=folders)
        return dict(fake.puts)

    def testFoldersAreStoredUnderTheirOwnPrefix(self, monkeypatch, tmp_path):
        stored = self.write(monkeypatch, tmp_path,
                            [{"_id": "f1", "name": "Chapter 1", "type": "JournalEntry",
                              "folder": None, "sorting": "m", "sort": 100000}])
        assert "!folders!f1" in stored
        assert stored["!folders!f1"]["sorting"] == "m"

    def testAPackWithNoTreeWritesNoFolderKeys(self, monkeypatch, tmp_path):
        assert self.write(monkeypatch, tmp_path, []) == {}


class TestPackSelection(object):
    """Each pack gets its own type's folders, and nothing else (ADR-010)."""

    def database(self, tmp_path, filename, campaign=None):
        from entities.base import DatabaseFile

        converter = FakeConverter(tmp_path, campaign or makeCampaign(),
                                  export_as_module=True)
        database = DatabaseFile(converter, filename)
        converter.folders = Folders(converter)
        return database

    def campaign(self):
        return makeCampaign(
            journalfolder=[{"id": "f1", "n": "Chapter 1", "i": ["h1", "c1"]}],
            handouts=[{"id": "h1", "name": "Rumours", "archived": False}],
            characters=[{"id": "c1", "name": "Goblin", "archived": False}])

    def testJournalPackGetsOnlyJournalFolders(self, tmp_path):
        database = self.database(tmp_path, "journal.db", self.campaign())
        types = {folder["type"] for folder in database._packFolders()}
        assert types == {"JournalEntry"}

    def testActorPackGetsOnlyActorFolders(self, tmp_path):
        database = self.database(tmp_path, "actors.db", self.campaign())
        types = {folder["type"] for folder in database._packFolders()}
        assert types == {"Actor"}

    def testAnUnmappedPackCarriesNoTree(self, tmp_path):
        database = self.database(tmp_path, "fog.db", self.campaign())
        assert database._packFolders() == []

    def testSaveWritesTheTreeBesideTheDocuments(self, monkeypatch, tmp_path):
        database = self.database(tmp_path, "journal.db", self.campaign())
        database.entities = [StubEntity({"_id": "h1", "name": "Rumours"})]
        fake = FakePlyvel()
        monkeypatch.setattr(leveldb_pack, "plyvel", fake)
        database.save()
        stored = dict(fake.puts)
        assert "!journal!h1" in stored
        folders = [key for key in stored if key.startswith("!folders!")]
        assert len(folders) == 1
        assert stored[folders[0]]["name"] == "Chapter 1"


class StubEntity(object):
    def __init__(self, entity):
        self.entity = entity

