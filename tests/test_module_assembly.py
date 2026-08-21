"""Self-contained module assembly regressions (v1.14.0)."""

import copy
import os

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
        self.macros = Database()
        self.folders = Database()
        self.packs = {}
        for database in (self.journal, self.actors, self.items, self.scenes,
                         self.playlists, self.tables, self.decks, self.cards, self.macros,
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

    def test_macros_join_adventure_macros(self, tmp_path):
        converter = Converter(tmp_path)
        converter.macros = Database([Document({
            "_id": "macro00000000001", "name": "Roll", "type": "chat",
            "command": "[[1t[Encounter]]]", "folder": None,
        })])
        adventure = ModuleAssembler(converter).buildAdventure()
        assert [document["_id"] for document in adventure["macros"]] == [
            "macro00000000001"]

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

    def test_external_rolltable_link_in_prose_is_localized_when_donor_exists(self, tmp_path):
        converter = Converter(tmp_path)
        identifier = "table00000000001"
        source_uuid = "Compendium.custom-module.roll-tables.RollTable.%s" % identifier
        converter.items.entities = [Document({
            "_id": "spell00000000001", "name": "Confusion", "type": "spell",
            "system": {"description": {"value": "@UUID[%s]{Behavior}" % source_uuid}},
        })]
        donor = Document({
            "_id": identifier, "name": "Confusion: Behavior", "folder": None,
            "formula": "1d10", "results": [],
        }, package="custom-module", pack="roll-tables")
        donor._database._document_type = "RollTable"
        converter.packs = {"rolltables": Database([donor])}

        ModuleAssembler(converter).localizeExecutableReferences()

        assert [entry.entity["_id"] for entry in converter.tables.entities] == [identifier]
        assert converter.items.entities[0].entity["system"]["description"]["value"] == \
            "@UUID[Compendium.test-module.tables.RollTable.%s]{Behavior}" % identifier

    def test_usable_system_actor_target_stays_external(self, tmp_path):
        converter = Converter(tmp_path)
        source_uuid = "Compendium.dnd5e.monsters.Actor.systemactor00001"
        converter.items.entities = [Document({
            "_id": "spell00000000001", "name": "Summon", "type": "spell",
            "img": "icons/summon.webp", "system": {"activities": {"summon": {
                "profiles": [{"uuid": source_uuid}],
            }}},
        })]
        donor = Document({
            "_id": "systemactor00001", "name": "Spirit", "type": "npc",
            "img": "icons/spirit.webp",
            "prototypeToken": {"texture": {"src": "icons/spirit-token.webp"}},
            "items": [], "effects": [],
        }, package="dnd5e", pack="monsters")
        converter.packs = {"monsters": Database([donor])}
        ModuleAssembler(converter).localizeExecutableReferences()
        profile = converter.items.entities[0].entity["system"]["activities"]["summon"]["profiles"][0]
        assert profile["uuid"] == source_uuid
        assert converter.actors.entities == []

    def test_null_art_system_actor_is_cloned_once_and_rewritten_everywhere(self, tmp_path):
        converter = Converter(tmp_path)
        source_uuid = "Compendium.dnd5e.monsters.Actor.zwT2WjWo7cTm2631"
        for index in range(2):
            converter.items.entities.append(Document({
                "_id": "spell000000000%02d" % index, "name": "Mage Hand",
                "type": "spell", "img": "icons/magic/hand.webp",
                "system": {"activities": {"summon": {
                    "profiles": [{"_id": "profile000000%03d" % index,
                                  "uuid": source_uuid}],
                }}},
            }))
        donor = Document({
            "_id": "zwT2WjWo7cTm2631", "name": "Mage Hand", "type": "npc",
            "img": None, "prototypeToken": {"texture": {"src": None}},
            "items": [], "effects": [],
        }, package="dnd5e", pack="monsters")
        converter.packs = {"monsters": Database([donor])}

        ModuleAssembler(converter).localizeExecutableReferences()

        assert len(converter.actors.entities) == 1
        clone = converter.actors.entities[0].entity
        assert clone["_id"] == "zwT2WjWo7cTm2631"
        assert clone["img"] == "icons/magic/hand.webp"
        assert clone["prototypeToken"]["texture"]["src"] == "icons/magic/hand.webp"
        assert clone["prototypeToken"]["displayName"] == 40
        expected = "Compendium.test-module.actors.Actor.zwT2WjWo7cTm2631"
        assert all(item.entity["system"]["activities"]["summon"]["profiles"][0]["uuid"] == expected
                   for item in converter.items.entities)

    def test_null_art_system_actor_without_item_icon_fails_with_uuid(self, tmp_path):
        converter = Converter(tmp_path)
        source_uuid = "Compendium.dnd5e.monsters.Actor.zwT2WjWo7cTm2631"
        converter.items.entities = [Document({
            "_id": "spell00000000001", "name": "Mage Hand", "type": "spell",
            "img": None, "system": {"activities": {"summon": {
                "profiles": [{"uuid": source_uuid}],
            }}},
        })]
        donor = Document({
            "_id": "zwT2WjWo7cTm2631", "name": "Mage Hand", "type": "npc",
            "img": None, "prototypeToken": {"texture": {"src": None}},
            "items": [], "effects": [],
        }, package="dnd5e", pack="monsters")
        converter.packs = {"monsters": Database([donor])}
        with pytest.raises(ValueError, match="zwT2WjWo7cTm2631"):
            ModuleAssembler(converter).localizeExecutableReferences()

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
        assert all(folder["_stats"]["coreVersion"] == "13" for folder in folders)
        assert all(folder["_stats"]["systemVersion"] == "5.3.3" for folder in folders)
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

    def test_placeholder_removes_the_complete_html_image_tag(self, tmp_path):
        converter = Converter(tmp_path)
        document = Document({
            "_id": "journal000000001", "name": "Portrait", "type": "journal",
            "pages": [{"text": {"content":
                '<p>Before</p><img class="dead" src="https://imgsrv.roll20.net/dead.png"><p>After</p>'}}],
        })
        converter.journal.entities = [document]
        assembler = ModuleAssembler(converter)

        def placeholder(url):
            raise __import__("entities.base", fromlist=["Roll20PlaceholderError"]).Roll20PlaceholderError(url)

        assembler._copyExternalAsset = placeholder
        assembler.internalizeAssets()
        content = document.entity["pages"][0]["text"]["content"]
        assert content == "<p>Before</p><p>After</p>"
        assert assembler.placeholder_urls == {"https://imgsrv.roll20.net/dead.png"}
        assert assembler.placeholder_references == 1
        assert assembler.placeholder_tags_stripped == 1
        assert not (tmp_path / "assets").exists()

    def test_unrecoverable_bare_img_removes_the_complete_tag(self, tmp_path):
        converter = Converter(tmp_path)
        document = Document({
            "_id": "journal000000001", "name": "Gears", "type": "journal",
            "pages": [{"text": {"content":
                '<p>Before</p><img src="0_DnD_EFA_Intro_Gear1..jpg"><p>After</p>'}}],
        })
        converter.journal.entities = [document]
        assembler = ModuleAssembler(converter)

        assembler.internalizeAssets()

        assert document.entity["pages"][0]["text"]["content"] == \
            "<p>Before</p><p>After</p>"
        assert assembler.missing_relative_assets == {"0_DnD_EFA_Intro_Gear1..jpg"}
        assert assembler.missing_relative_tags_stripped == 1

    def test_unique_relative_img_is_copied_from_the_source_zip(self, tmp_path):
        converter = Converter(tmp_path)
        converter.zip = type("Archive", (), {
            "namelist": lambda self: ["journal/001 - Gears/gear.jpg"],
        })()
        document = Document({
            "_id": "journal000000001", "name": "Gears", "type": "journal",
            "pages": [{"text": {"content": '<img src="gear.jpg">'}}],
        })
        converter.journal.entities = [document]
        assembler = ModuleAssembler(converter)
        copied = []
        helper = type("Helper", (), {
            "copyZipFile": lambda self, url, source, destination, **kwargs:
                (copied.append((url, source, destination, kwargs)) or
                 ("asset", "modules/test-module/assets/html/gear.jpg")),
        })()
        assembler._assetHelper = lambda: helper

        assembler.internalizeAssets()

        assert copied == [("gear.jpg", "journal/001 - Gears/gear.jpg",
                   os.path.join("assets", "html", "embedded"),
                   {"type": "html", "dedup": True})]
        assert document.entity["pages"][0]["text"]["content"] == \
            '<img src="modules/test-module/assets/html/gear.jpg">'

    def test_ambiguous_relative_img_fails_closed(self, tmp_path):
        converter = Converter(tmp_path)
        converter.zip = type("Archive", (), {
            "namelist": lambda self: ["journal/001/gear.jpg", "journal/002/gear.jpg"],
        })()
        assembler = ModuleAssembler(converter)
        with pytest.raises(ValueError, match="ambiguous"):
            assembler._copyRelativeAsset("gear.jpg")

    def test_placeholder_in_structural_image_field_fails_closed(self, tmp_path):
        converter = Converter(tmp_path)
        converter.actors.entities = [Document({
            "_id": "actor00000000001", "name": "Portrait", "type": "npc",
            "img": "https://imgsrv.roll20.net/dead.png", "items": [], "effects": [],
        })]
        assembler = ModuleAssembler(converter)
        error = __import__("entities.base", fromlist=["Roll20PlaceholderError"]).Roll20PlaceholderError
        assembler._copyExternalAsset = lambda url: (_ for _ in ()).throw(error(url))
        with pytest.raises(error, match="dead.png"):
            assembler.internalizeAssets()