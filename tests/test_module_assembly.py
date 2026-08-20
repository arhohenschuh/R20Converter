"""Self-contained module assembly regressions (v1.14.0)."""

import copy

import pytest

from module_assembly import ModuleAssembler


class Document(object):
    def __init__(self, entity, package=None, pack=None):
        self.entity = copy.deepcopy(entity)
        self._database = type("SourceDB", (), {
            "_package": package,
            "_pack_name": pack,
        })()

    def getFullID(self):
        return "%s.%s.%s" % (
            self._database._package, self._database._pack_name,
            self.entity["_id"])


class Database(object):
    def __init__(self, entities=()):
        self.entities = list(entities)


class Converter(object):
    def __init__(self, tmp_path):
        self.path = str(tmp_path)
        self.name = "test-module"
        self.game_system = "dnd5e"
        self.game_system_version = "5.3.3"
        self.campaign = {"campaign_title": "Test Adventure"}
        self._arguments = {"package_version": "1.14.0"}
        self.journal = Database()
        self.actors = Database()
        self.items = Database()
        self.scenes = Database()
        self.playlists = Database()
        self.tables = Database()
        self.decks = Database()
        self.cards = Database()
        self.folders = Database()
        self.packs = {}
        for database in (self.journal, self.actors, self.items, self.scenes,
                         self.playlists, self.tables, self.decks, self.cards,
                         self.folders):
            database._converter = self

    def getArgument(self, name, default=None):
        return self._arguments.get(name, default)


def actor(identifier="actor00000000001", name="Goblin"):
    return Document({"_id": identifier, "name": name, "type": "npc",
                     "folder": "folder0000000001", "items": [], "effects": []})


def scene(actor_id="actor00000000001"):
    return Document({"_id": "scene00000000001", "name": "Cave",
                     "folder": None, "tokens": [{"_id": "token00000000001",
                                                   "actorId": actor_id}]})


def folder():
    return Document({"_id": "folder0000000001", "name": "Creatures",
                     "type": "Actor", "folder": None, "sort": 100000})


class TestAdventureAssembly(object):
    def test_preserves_document_and_folder_ids(self, tmp_path):
        converter = Converter(tmp_path)
        converter.actors.entities = [actor()]
        converter.scenes.entities = [scene()]
        converter.folders.entities = [folder()]
        adventure = ModuleAssembler(converter).buildAdventure()
        assert [document["_id"] for document in adventure["actors"]] == ["actor00000000001"]
        assert adventure["actors"][0]["folder"] == "folder0000000001"
        assert [entry["_id"] for entry in adventure["folders"]] == ["folder0000000001"]
        assert adventure["scenes"][0]["tokens"][0]["actorId"] == "actor00000000001"

    def test_item_typed_deck_cards_join_adventure_items(self, tmp_path):
        converter = Converter(tmp_path)
        converter.cards.entities = [Document({
            "_id": "carditem00000001", "name": "Ace", "type": "loot",
            "folder": None,
        })]
        adventure = ModuleAssembler(converter).buildAdventure()
        assert [document["_id"] for document in adventure["items"]] == [
            "carditem00000001"]
        assert adventure["cards"] == []

    def test_rejects_a_broken_token_actor_link(self, tmp_path):
        converter = Converter(tmp_path)
        converter.actors.entities = [actor()]
        converter.scenes.entities = [scene("missing000000001")]
        converter.folders.entities = [folder()]
        with pytest.raises(ValueError, match="token actor link"):
            ModuleAssembler(converter).buildAdventure()


class TestExecutableReferences(object):
    def test_custom_actor_target_is_cloned_and_rewritten_locally(self, tmp_path):
        converter = Converter(tmp_path)
        source_uuid = "Compendium.custom-module.summons.Actor.summon0000000001"
        converter.items.entities = [Document({
            "_id": "spell00000000001", "name": "Summon", "type": "spell",
            "system": {"activities": {"summon": {
                "type": "summon", "profiles": [{"uuid": source_uuid}],
            }}},
        })]
        donor = Document({"_id": "summon0000000001", "name": "Spirit",
                          "type": "npc", "folder": "external-folder",
                          "prototypeToken": {"displayName": 0},
                          "items": [], "effects": []},
                         package="custom-module", pack="summons")
        converter.packs = {"monsters": Database([donor])}

        assembler = ModuleAssembler(converter)
        assembler.localizeExecutableReferences()

        assert [entry.entity["_id"] for entry in converter.actors.entities] == [
            "summon0000000001"]
        profile = converter.items.entities[0].entity["system"]["activities"]["summon"]["profiles"][0]
        assert profile["uuid"] == \
            "Compendium.test-module.actors.Actor.summon0000000001"
        assert converter.actors.entities[0].entity["folder"] is None
        assert converter.actors.entities[0].entity["prototypeToken"]["displayName"] == 40

    def test_unresolvable_executable_target_is_rejected(self, tmp_path):
        converter = Converter(tmp_path)
        converter.items.entities = [Document({
            "_id": "spell00000000001", "name": "Summon", "type": "spell",
            "system": {"activities": {"summon": {"profiles": [{
                "uuid": "Compendium.missing.actors.Actor.missing000000001",
            }]}}},
        })]
        with pytest.raises(ValueError, match="executable compendium reference"):
            ModuleAssembler(converter).localizeExecutableReferences()

    def test_malformed_executable_target_is_rejected(self, tmp_path):
        converter = Converter(tmp_path)
        converter.items.entities = [Document({
            "_id": "spell00000000001", "name": "Summon", "type": "spell",
            "system": {"activities": {"summon": {"profiles": [{
                "uuid": "Compendium.custom.actors.Actor.short",
            }]}}},
        })]
        with pytest.raises(ValueError, match="invalid executable compendium reference"):
            ModuleAssembler(converter).localizeExecutableReferences()

    def test_broken_same_module_executable_target_is_rejected(self, tmp_path):
        converter = Converter(tmp_path)
        converter.items.entities = [Document({
            "_id": "spell00000000001", "name": "Summon", "type": "spell",
            "system": {"activities": {"summon": {"profiles": [{
                "uuid": "Compendium.test-module.actors.Actor.missing000000001",
            }]}}},
        })]
        with pytest.raises(ValueError, match="local executable compendium reference"):
            ModuleAssembler(converter).localizeExecutableReferences()

    def test_same_module_card_item_target_resolves(self, tmp_path):
        converter = Converter(tmp_path)
        identifier = "carditem00000001"
        converter.cards.entities = [Document({
            "_id": identifier, "name": "Ace", "type": "loot", "folder": None,
        })]
        converter.tables.entities = [Document({
            "_id": "table00000000001", "name": "Deck", "type": "table",
            "results": [{"documentUuid":
                "Compendium.test-module.cards.Item.%s" % identifier}],
        })]
        ModuleAssembler(converter).localizeExecutableReferences()

    def test_external_prose_link_becomes_a_recommendation(self, tmp_path):
        converter = Converter(tmp_path)
        converter.journal.entities = [Document({
            "_id": "journal000000001", "name": "Rules", "type": "journal",
            "pages": [{"text": {"content":
                "@UUID[Compendium.optional-library.rules.JournalEntry.rule00000000001]{Rule}"}}],
        })]
        recommendations = ModuleAssembler(converter).collectRecommendations()
        assert recommendations == {"optional-library"}

    def test_external_item_link_in_prose_is_localized_when_donor_exists(self, tmp_path):
        converter = Converter(tmp_path)
        identifier = "donoritem0000001"
        source_uuid = "Compendium.custom-module.items.Item.%s" % identifier
        converter.journal.entities = [Document({
            "_id": "journal000000001", "name": "Rules", "type": "journal",
            "pages": [{"text": {"content": "@UUID[%s]{Wand}" % source_uuid}}],
        })]
        donor = Document({"_id": identifier, "name": "Wand", "type": "loot",
                          "folder": None}, package="custom-module", pack="items")
        converter.packs = {"items": Database([donor])}
        ModuleAssembler(converter).localizeExecutableReferences()
        assert converter.journal.entities[0].entity["pages"][0]["text"]["content"] == \
            "@UUID[Compendium.test-module.items.Item.%s]{Wand}" % identifier

    def test_source_journal_hierarchy_is_projected(self, tmp_path):
        converter = Converter(tmp_path)
        source_id = "-source-handout"
        journal_id = __import__("entities.base", fromlist=["Entity"]).Entity.normalizeID(source_id)
        converter.campaign.update({
            "handouts": [{"id": source_id, "name": "Note"}],
            "characters": [],
            "journalfolder": [{"n": "Root", "i": [
                {"n": "Chapter", "i": [source_id]}]}],
        })
        converter.journal.entities = [Document({
            "_id": journal_id, "name": "Note", "folder": None, "sort": 0,
        })]
        assembler = ModuleAssembler(converter)
        assembler.normalizeJournalHierarchy()
        folders = [entity.entity for entity in converter.folders.entities]
        assert [folder["name"] for folder in folders] == ["Root", "Chapter"]
        assert folders[1]["folder"] == folders[0]["_id"]
        assert converter.journal.entities[0].entity["folder"] == folders[1]["_id"]


class TestEmbeddedHtmlArt(object):
    def test_external_img_is_rewritten_through_existing_asset_copier(self, tmp_path):
        converter = Converter(tmp_path)
        document = Document({
            "_id": "journal000000001", "name": "Portrait", "type": "journal",
            "pages": [{"text": {"content": '<p><img src="https://files.d20.io/images/1/face.png"></p>'}}],
        })
        converter.journal.entities = [document]
        assembler = ModuleAssembler(converter)
        copied = []

        def copy(url):
            copied.append(url)
            return "modules/test-module/assets/html/face.webp"

        assembler._copyExternalAsset = copy
        assembler.internalizeAssets()
        content = document.entity["pages"][0]["text"]["content"]
        assert copied == ["https://files.d20.io/images/1/face.png"]
        assert 'src="modules/test-module/assets/html/face.webp"' in content

    def test_failed_external_img_copy_aborts_assembly(self, tmp_path):
        converter = Converter(tmp_path)
        converter.journal.entities = [Document({
            "_id": "journal000000001", "name": "Portrait", "type": "journal",
            "pages": [{"text": {"content": '<img src="https://example.invalid/missing.png">'}}],
        })]
        assembler = ModuleAssembler(converter)
        assembler._copyExternalAsset = lambda url: ""
        with pytest.raises(ValueError, match="could not internalize"):
            assembler.internalizeAssets()