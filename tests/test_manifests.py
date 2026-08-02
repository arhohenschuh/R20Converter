"""Tests for the ``world.json`` and ``module.json`` manifests.

These assert the Foundry v13 manifest schema decided in ADR-002, including the
absence of the fields Foundry removed -- a manifest that still carries `name`,
`entity` or `minimumCoreVersion` is the failure mode this suite exists to catch.
"""

import json

import pytest

import foundry
from module import DEFAULT_PACK_OWNERSHIP, Module
from world import World


class FakeDB(object):
    def __init__(self, entities=()):
        self.entities = list(entities)
        self.saved = False

    def save(self):
        self.saved = True
        return self


class FakeConverter(object):
    """Just enough converter for the manifest builders."""

    def __init__(self, tmp_path, **arguments):
        self.path = str(tmp_path)
        self.name = "my-campaign"
        self.campaign = {"campaign_title": "My Campaign"}
        self.game_system = "dnd5e"
        self.game_system_version = "2.4.1"
        self._arguments = {"description": "Imported from Roll20"}
        self._arguments.update(arguments)
        self.chat = FakeDB()
        for name in ("journal", "actors", "items", "scenes", "playlists",
                     "tables", "decks", "cards"):
            setattr(self, name, FakeDB())

    def getArgument(self, name, default=None):
        return self._arguments.get(name, default)


@pytest.fixture
def converter(tmp_path):
    return FakeConverter(tmp_path)


class TestWorldManifest(object):
    def test_uses_id_not_name(self, converter):
        manifest = World(converter).toDict()
        assert manifest["id"] == "my-campaign"
        # `name` was deprecated in v10 and is no longer read in v13.
        assert "name" not in manifest

    def test_declares_its_package_type(self, converter):
        assert World(converter).toDict()["type"] == "world"

    def test_uses_the_compatibility_object(self, converter):
        manifest = World(converter).toDict()
        assert manifest["compatibility"] == {"minimum": "13", "verified": "13"}
        assert "minimumCoreVersion" not in manifest
        assert "compatibleCoreVersion" not in manifest

    def test_core_version_matches_the_schema_we_emit(self, converter):
        # Foundry uses coreVersion to choose which migrations to run, so it must
        # describe our actual output rather than being an independent literal.
        manifest = World(converter).toDict()
        assert manifest["coreVersion"] == foundry.DOCUMENT_SCHEMA_CORE_VERSION

    def test_uses_relationships_not_dependencies(self, converter):
        manifest = World(converter).toDict()
        assert "dependencies" not in manifest
        # The documents we emit use the dnd5e 5.x schema and are unreadable by
        # older releases (ADR-008), so a minimum is declared as well as the
        # verified version: installing against an older system should fail
        # loudly rather than produce items the system cannot parse.
        assert manifest["relationships"]["systems"] == [
            {"id": "dnd5e", "type": "system",
             "compatibility": {"minimum": foundry.MINIMUM_SYSTEM_VERSION,
                               "verified": "2.4.1"}}
        ]

    def test_title_falls_back_to_the_campaign_title(self, converter):
        assert World(converter).toDict()["title"] == "My Campaign"

    def test_title_can_be_overridden(self, tmp_path):
        converter = FakeConverter(tmp_path, campaign_title="Renamed")
        assert World(converter).toDict()["title"] == "Renamed"

    def test_roll20_templates_are_only_declared_when_chat_was_converted(self, converter):
        assert World(converter).toDict()["scripts"] == []
        converter.chat.entities.append(object())
        manifest = World(converter).toDict()
        assert manifest["scripts"] == ["templates/roll20-templates.js"]
        assert manifest["styles"] == ["templates/roll20-templates.css"]

    def test_manifest_is_serialisable(self, converter):
        assert json.loads(str(World(converter)))["id"] == "my-campaign"

    def test_save_writes_world_json(self, converter, tmp_path):
        World(converter).save()
        written = json.loads((tmp_path / "world.json").read_text())
        assert written["type"] == "world"


class TestModuleManifest(object):
    def test_uses_id_and_type(self, converter):
        manifest = Module(converter).toDict()
        assert manifest["id"] == "my-campaign"
        assert manifest["type"] == "module"
        assert "name" not in manifest

    def test_uses_the_compatibility_object(self, converter):
        manifest = Module(converter).toDict()
        assert manifest["compatibility"] == {"minimum": "13", "verified": "13"}
        assert "minimumCoreVersion" not in manifest
        assert "compatibleCoreVersion" not in manifest

    def test_uses_authors_array_not_author_string(self, converter):
        manifest = Module(converter).toDict()
        assert manifest["authors"] == [{"name": "R20Converter"}]
        assert "author" not in manifest

    def test_no_packs_when_everything_is_empty(self, converter):
        assert Module(converter).toDict()["packs"] == []

    def test_populated_collections_become_packs(self, converter):
        converter.actors.entities.append(object())
        pack, = Module(converter).toDict()["packs"]
        assert pack["name"] == "actors"
        assert pack["label"] == "Actors (My Campaign)"
        assert pack["system"] == "dnd5e"

    def test_pack_uses_type_not_entity(self, converter):
        # `entity` was renamed to `type` in v10 and removed in v13.
        converter.journal.entities.append(object())
        pack, = Module(converter).toDict()["packs"]
        assert pack["type"] == "JournalEntry"
        assert "entity" not in pack

    def test_pack_path_has_no_db_extension(self, converter):
        # In v13 a pack path names a LevelDB directory, not a NeDB file.
        converter.scenes.entities.append(object())
        pack, = Module(converter).toDict()["packs"]
        assert pack["path"] == "packs/scenes"

    def test_pack_declares_ownership(self, converter):
        converter.items.entities.append(object())
        pack, = Module(converter).toDict()["packs"]
        assert pack["ownership"] == DEFAULT_PACK_OWNERSHIP
        assert "private" not in pack

    def test_ownership_uses_valid_roles_and_levels(self):
        assert set(DEFAULT_PACK_OWNERSHIP) <= {"PLAYER", "TRUSTED", "ASSISTANT", "GAMEMASTER"}
        assert set(DEFAULT_PACK_OWNERSHIP.values()) <= {"NONE", "LIMITED", "OBSERVER", "OWNER"}

    def test_non_empty_collections_are_saved(self, converter):
        converter.actors.entities.append(object())
        Module(converter)
        assert converter.actors.saved is True
        assert converter.scenes.saved is False

    def test_save_writes_module_json(self, converter, tmp_path):
        Module(converter).save()
        written = json.loads((tmp_path / "module.json").read_text())
        assert written["id"] == "my-campaign"


class TestFoundryConstants(object):
    def test_compatibility_defaults_to_the_target_generation(self):
        assert foundry.compatibility() == {"minimum": "13", "verified": "13"}

    def test_compatibility_omits_maximum(self):
        # A maximum would block installation on untested future generations.
        assert "maximum" not in foundry.compatibility()

    def test_system_relationship_without_a_version(self):
        assert foundry.systemRelationship("pf2e") == {"id": "pf2e", "type": "system"}

    def test_system_relationship_with_a_version(self):
        assert foundry.systemRelationship("pf2e", "6.0.0")["compatibility"] == {"verified": "6.0.0"}
