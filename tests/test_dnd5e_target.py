"""dnd5e output target selection, the 6.x document profile, and B125-B127.

The converter writes one dnd5e generation's document schema. dnd5e 6 migrates
5.x fields only in memory, through shims due for removal in 7.0, so a 6.x target
must store the 6.x shape itself. These tests pin that shape against the 6.0.6
migrations it mirrors and keep the 5.3.3 target byte-for-byte unchanged.
"""

import copy
import json
from types import SimpleNamespace

import pytest

import dnd5e
import foundry
from R20Converter import R20Converter
from entities.actors import Token
from entities.base import Entity
from entities.items import ItemActivation
from entities.settings import SettingsDB

from conftest import FakeDatabase
from test_asset_and_compendium_fixes import (FeatBoundaryActor, InventoryBoundaryActor,
                                             StubOwnedItem, _inventory_donor)


def _database(entities, filename):
    return SimpleNamespace(_filename=filename,
                           entities=[SimpleNamespace(entity=entity) for entity in entities])


def _converter(version="6.0.6", actors=()):
    converter = R20Converter.__new__(R20Converter)
    converter.game_system = "dnd5e"
    converter.game_system_version = version
    by_id = {actor["_id"]: SimpleNamespace(entity=actor) for actor in actors}
    converter.actors = SimpleNamespace(getById=by_id.get)
    return converter


def _legacy_actor(size="sm"):
    return {
        "_id": "actor00000000001",
        "type": "npc",
        "prototypeToken": {"flags": {}, "ring": {"enabled": False}},
        "system": {
            "abilities": {"str": {"value": 10, "bonuses": {"check": "1", "save": ""}}},
            "skills": {"acr": {"value": 0, "ability": "dex",
                               "bonuses": {"check": "2", "passive": ""}}},
            "attributes": {
                "ac": {"flat": 15, "calc": "flat", "formula": ""},
                "init": {"ability": "", "bonus": "2"},
                "movement": {"walk": 30, "fly": 0, "units": "ft", "hover": False},
            },
            "bonuses": {"mwak": {"attack": "1", "damage": ""},
                        "abilities": {"check": "", "save": "1", "skill": ""}},
            "traits": {"size": size},
        },
        "items": [{
            "_id": "item000000000001",
            "type": "weapon",
            "system": {"rarity": "veryRare", "properties": ["mgc"]},
            "effects": [{
                "_id": "effect0000000001",
                "changes": [{"key": "system.attributes.ac.base", "mode": 2, "value": "1"}],
                "_stats": {"systemVersion": "5.3.3"},
            }],
        }],
        "effects": [],
    }


class TestTargetSelection(object):
    @pytest.mark.parametrize("argument,version", [(None, "6.0.6"), ("6.x", "6.0.6"), ("5.3.3", "5.3.3")])
    def test_converter_records_the_selected_target(self, tmp_path, argument, version):
        args = SimpleNamespace(path=str(tmp_path), zip_file=None, json=True, dnd5e_version=argument)
        (tmp_path / "campaign.json").write_text("{}", encoding="utf-8")
        args.zip_file = str(tmp_path / "campaign.json")
        args.fvtt_data_path = str(tmp_path / "missing")
        converter = R20Converter(args, logger=SimpleNamespace(
            logInfo=lambda *a, **k: None, logWarning=lambda *a, **k: None,
            logError=lambda *a, **k: None))
        assert converter.game_system_version == version
        settings = {entity.entity["key"]: json.loads(entity.entity["value"])
                    for entity in SettingsDB(converter).entities}
        assert settings["dnd5e.systemMigrationVersion"] == version

    def test_cli_defaults_to_the_six_point_x_target(self):
        import main
        assert main.parser.parse_args(["out", "in.zip"]).dnd5e_version == "6.x"
        assert main.parser.parse_args(["out", "in.zip", "--dnd5e-version", "5.3.3"]).dnd5e_version == "5.3.3"
        with pytest.raises(SystemExit):
            main.parser.parse_args(["out", "in.zip", "--dnd5e-version", "4.4.1"])

    @pytest.mark.parametrize("version,minimum", [("6.0.6", "6.0.0"), ("5.3.3", "5.0.0")])
    def test_manifest_minimum_follows_the_target(self, version, minimum):
        assert foundry.systemRelationship("dnd5e", version)["compatibility"] == {
            "minimum": minimum, "verified": version}


class TestSixPointXProfile(object):
    """Mirrors dnd5e 6.0.6 ``_migrateArmorClass``, ``#migrateBonusData`` and friends."""

    def _finalize(self, version="6.0.6", size="sm"):
        actor = _legacy_actor(size)
        converter = _converter(version, [actor])
        converter.finalizeSystemDocuments(_database([actor], "actors.db"))
        return actor

    def test_actor_system_is_written_in_six_point_x_shape(self):
        system = self._finalize()["system"]
        ac = system["attributes"]["ac"]
        assert ac == {"flat": 15, "override": 15, "calcs": ["unarmored", "armored"], "formulas": []}
        init = system["attributes"]["init"]
        assert init == {"ability": "", "roll": {"min": None, "max": None, "mode": 0, "bonus": "2"}}
        assert system["attributes"]["movement"] == {
            "units": "ft", "hover": False, "speeds": {"walk": "30", "fly": "0"}}
        assert system["rolls"]["attack"]["mwak"]["bonus"] == "1"
        assert system["rolls"]["ability"]["save"]["bonus"] == "1"
        assert "mwak" not in system["bonuses"] and "abilities" not in system["bonuses"]
        assert system["abilities"]["str"] == {"value": 10, "check": {"roll": {"bonus": "1"}}}
        assert system["skills"]["acr"]["roll"] == {"bonus": "2"}
        assert system["skills"]["acr"]["bonuses"] == {"passive": ""}

    @pytest.mark.parametrize("calc,formula,expected", [
        ("default", "", {"calcs": ["unarmored", "armored"], "formulas": []}),
        ("natural", "", {"calcs": ["natural"], "formulas": []}),
        ("mage", "", {"calcs": ["unarmored", "armored", "mage"], "formulas": []}),
        ("custom", "12 + @abilities.dex.mod",
         {"calcs": ["unarmored", "armored"], "formulas": [{"formula": "12 + @abilities.dex.mod"}]}),
    ])
    def test_armor_class_calculations(self, calc, formula, expected):
        system = {"attributes": {"ac": {"flat": None, "calc": calc, "formula": formula}}}
        dnd5e.upgradeActorSystem6(system)
        expected = dict(expected, flat=None)
        assert system["attributes"]["ac"] == expected

    def test_small_creatures_keep_their_token_scale(self):
        assert self._finalize(size="sm")["prototypeToken"]["flags"] == {"dnd5e": {"lockScale": True}}
        assert self._finalize(size="med")["prototypeToken"]["flags"] == {}
        ringed = {"flags": {}, "ring": {"enabled": True}}
        assert dnd5e.lockSmallTokenScale(ringed, "sm")["flags"] == {}

    def test_items_and_effects_are_migrated_deterministically(self):
        first, second = self._finalize(), self._finalize()
        item = first["items"][0]
        assert item["system"]["rarities"] == ["veryRare"] and "rarity" not in item["system"]
        effect = item["effects"][0]
        change = effect["changes"][0]
        assert change["key"] == "system.attributes.ac.armor"
        assert len(change["_id"]) == 16
        assert change["_id"] == second["items"][0]["effects"][0]["changes"][0]["_id"]
        assert effect["system"]["magical"] is True
        assert effect["_stats"]["systemVersion"] == "6.0.6"

    def test_finalizing_twice_is_a_fixed_point(self):
        actor = self._finalize()
        once = copy.deepcopy(actor)
        converter = _converter("6.0.6", [actor])
        converter.finalizeSystemDocuments(_database([actor], "actors.db"))
        assert actor == once

    def test_six_point_x_authored_effects_are_left_alone(self):
        effect = {"_id": "native0000000001", "changes": [{"key": "system.attributes.ac.base"}],
                  "system": {"magical": False}, "_stats": {"systemVersion": "6.0.5"}}
        before = copy.deepcopy(effect)
        dnd5e.upgradeEffect6(effect, {"type": "spell"}, "seed")
        assert effect == before

    def test_five_point_three_target_is_untouched(self):
        actor = _legacy_actor()
        before = copy.deepcopy(actor)
        converter = _converter("5.3.3", [actor])
        converter.finalizeSystemDocuments(_database([actor], "actors.db"))
        assert actor == before

    def test_placed_small_tokens_lock_scale(self):
        small, medium = _legacy_actor("sm"), _legacy_actor("med")
        medium["_id"] = "actor00000000002"
        scene = {"tokens": [{"actorId": small["_id"], "flags": {}},
                            {"actorId": medium["_id"], "flags": {}},
                            {"actorId": None, "flags": {}}]}
        converter = _converter("6.0.6", [small, medium])
        converter.finalizeSystemDocuments(_database([scene], "scenes.db"))
        assert [token["flags"] for token in scene["tokens"]] == [{"dnd5e": {"lockScale": True}}, {}, {}]

    def test_world_items_lose_legacy_rarity(self):
        item = {"_id": "worlditem0000001", "type": "equipment", "system": {"rarity": ""}}
        _converter().finalizeSystemDocuments(_database([item], "items.db"))
        assert item["system"] == {"rarities": []}


class SourceOnlyItems(object):
    """Items database that never matches a donor and records emitted artwork."""

    def createItemSubclass(self, identifier, name, description, class_name):
        return StubOwnedItem({"_id": "subclass00000001", "name": name, "type": "subclass", "img": None})

    def createItemRace(self, identifier, name):
        return StubOwnedItem({"_id": "race000000000001", "name": name, "type": "race", "img": None})

    def createItemBackground(self, identifier, name):
        return StubOwnedItem({"_id": "background000001", "name": name, "type": "background", "img": None})


def _icon_converter(tmp_path):
    converter = R20Converter.__new__(R20Converter)
    portrait = "modules/donor/monsters/wolf.webp"
    converter.packs = {
        "items": _database([{"name": "Longsword", "type": "weapon", "img": "icons/longsword.webp"}],
                           "items.db"),
        "classfeatures": _database([{"name": "Multiattack", "type": "feat", "img": "icons/hunter.webp"}],
                                   "classfeatures.db"),
        "monsters": _database([{
            "name": "Wolf", "img": portrait, "prototypeToken": {"texture": {"src": "tokens/wolf.webp"}},
            "items": [{"name": "Bite", "type": "weapon", "img": portrait},
                      {"name": "Pack Tactics", "type": "feat", "img": "tokens/wolf.webp"},
                      {"name": "Multiattack", "type": "feat", "img": "icons/monster-multiattack.webp"}],
        }], "monsters.db"),
    }
    return converter


class TestB125ItemArtwork(object):
    """Unmatched owned items must never inherit the actor's portrait or token."""

    def test_unmatched_item_uses_the_type_default(self, tmp_path):
        actor = InventoryBoundaryActor(FakeDatabase(str(tmp_path)))
        item = actor.createItemInventory([], "Glaive of Dawn", "", "weapon",
                                         object(), object(), object(), object())
        assert item["img"] == dnd5e.defaultItemIcon("weapon")

    def test_donor_artwork_is_kept(self, tmp_path):
        actor = InventoryBoundaryActor(FakeDatabase(str(tmp_path)), _inventory_donor("Shovel", "equipment"))
        item = actor.createItemInventory([], "Shovel", "", "weapon",
                                         object(), object(), object(), object())
        assert item["img"] == "icons/donor.webp"

    def test_donor_artwork_equal_to_the_portrait_is_rejected(self, tmp_path):
        donor = _inventory_donor("Shovel", "equipment")
        donor.entity["img"] = "source.webp"
        actor = InventoryBoundaryActor(FakeDatabase(str(tmp_path)), donor)
        item = actor.createItemInventory([], "Shovel", "", "weapon",
                                         object(), object(), object(), object())
        assert item["img"] == dnd5e.defaultItemIcon("weapon")

    def test_renamed_item_borrows_compendium_artwork(self, tmp_path):
        actor = InventoryBoundaryActor(FakeDatabase(str(tmp_path)))
        actor._converter.itemIconIndex = _icon_converter(tmp_path).itemIconIndex
        actor.isNPC = lambda: False
        item = actor.createItemInventory([], "Variant: +1 Longsword (Silvered).", "", "weapon",
                                         object(), object(), object(), object())
        assert item["img"] == "icons/longsword.webp"

    def test_monster_portraits_are_never_indexed(self, tmp_path):
        monster_typed, monster_untyped = _icon_converter(tmp_path).itemIconIndex()["monster"]
        assert "bite" not in monster_untyped and "pack tactics" not in monster_untyped
        assert monster_typed[("feat", "multiattack")] == "icons/monster-multiattack.webp"

    @pytest.mark.parametrize("npc,expected", [(True, "icons/monster-multiattack.webp"),
                                              (False, "icons/hunter.webp")])
    def test_lookup_prefers_the_actor_kind_source(self, tmp_path, npc, expected):
        database = FakeDatabase(str(tmp_path))
        database._arguments = {"no_compendium_overwrite": True}
        actor = FeatBoundaryActor(database, None, npc)
        actor._converter.itemIconIndex = _icon_converter(tmp_path).itemIconIndex
        item = actor.createItemFeat([], "Multiattack", "Two attacks.",
                                    ItemActivation(ItemActivation.ACTION, 1), None, None)
        assert item["img"] == expected

    def test_subclass_and_origins_use_type_defaults(self, tmp_path):
        actor = InventoryBoundaryActor(FakeDatabase(str(tmp_path)))
        actor._converter.items = SourceOnlyItems()
        owned = []
        actor.createItemSubclass(owned, "Circle of Stars", "Druid")
        actor.createItemOrigin(owned, "race", "Tiefling")
        actor.createItemOrigin(owned, "background", "Sage")
        assert [item["img"] for item in owned] == [dnd5e.defaultItemIcon(kind)
                                                   for kind in ("subclass", "race", "background")]
        assert all(item["img"] != "source.webp" for item in owned)

    @pytest.mark.parametrize("name,key", [
        ("Variant: +1 Longsword (Silvered).", "longsword"),
        ("Fire Breath (Recharge 5\u20136)", "fire breath"),
        ("Fire Breath (Recharge 5\u00e2\u20ac\u201c6)", "fire breath"),
        ("  Multiattack  ", "multiattack"),
    ])
    def test_icon_keys_normalize_presentation_noise(self, name, key):
        assert key in dnd5e.iconLookupKeys(name)

    def test_unknown_type_falls_back_to_the_core_icon(self):
        assert dnd5e.defaultItemIcon("mystery") == "icons/svg/item-bag.svg"


class TestB126RollTwentyFlags(object):
    """Roll20 checkboxes arrive as ``"on"``; Foundry reads that string as false."""

    @pytest.mark.parametrize("value,expected", [
        ("on", True), (True, True), ("true", True), ("off", False), ("", False),
        (False, False), (None, False), ("false", False)])
    def test_flag_parser(self, value, expected):
        assert Entity.roll20Flag(value) is expected

    @pytest.mark.parametrize("value,enabled", [("on", True), (True, True), ("", False), (False, False)])
    def test_token_sight_follows_roll20(self, value, enabled):
        token = Token("id", "Scout", {"legacy_lighting_enabled": False,
                                      "has_bright_light_vision": value})
        assert token.getDict()["sight"]["enabled"] is enabled

    def test_off_string_does_not_mirror_the_token(self):
        token = Token("id", "Scout", {"legacy_lighting_enabled": False, "fliph": "off", "flipv": ""})
        texture = token.getDict()["texture"]
        assert (texture["scaleX"], texture["scaleY"]) == (1, 1)

    def test_legacy_flag_string_selects_the_legacy_fields(self):
        token = {"legacy_lighting_enabled": "on", "light_hassight": "on", "has_bright_light_vision": False}
        assert Token.hasSight(token) is True
        token["legacy_lighting_enabled"] = "off"
        assert Token.hasSight(token) is False


class TestB127Initiative(object):
    """dnd5e 6 doubled a numeric init bonus that sat next to ``init.value``."""

    def _native_migration(self, init):
        # dnd5e 6.0.6 ``#migrateBonusData`` then ``_migrateInitiative``.
        init = copy.deepcopy(init)
        if init.get("bonus") and "bonus" not in init.get("roll", {}):
            init.setdefault("roll", {})["bonus"] = init["bonus"]
        if init.get("value") and not isinstance(init.get("bonus"), str):
            roll = init.setdefault("roll", {})
            if roll.get("bonus"):
                roll["bonus"] = "%s + %s" % (roll["bonus"], init["value"])
            else:
                roll["bonus"] = str(init["value"])
        return init.get("roll", {}).get("bonus")

    @pytest.mark.parametrize("bonus", [2, -1])
    def test_old_shape_doubles_and_new_shape_does_not(self, bonus):
        old = {"value": bonus, "bonus": bonus, "mod": 3, "prof": 0, "total": bonus + 3}
        assert self._native_migration(old) == "%s + %s" % (bonus, bonus)
        actor = InventoryBoundaryActor(FakeDatabase("."))
        actor.abilityModifier = lambda ability: 3
        actor.getAttributeInt = lambda name, default=0: {"initiative_bonus": bonus + 3}.get(name, default)
        new = actor.createAttributeInitiative()
        assert new == {"ability": "", "bonus": str(bonus)}
        assert self._native_migration(new) == str(bonus)
        system = {"attributes": {"init": new}}
        dnd5e.upgradeActorSystem6(system)
        assert system["attributes"]["init"]["roll"]["bonus"] == str(bonus)

    def test_no_bonus_is_empty(self):
        actor = InventoryBoundaryActor(FakeDatabase("."))
        actor.abilityModifier = lambda ability: 2
        actor.getAttributeInt = lambda name, default=0: {"initiative_bonus": 2}.get(name, default)
        assert actor.createAttributeInitiative() == {"ability": "", "bonus": ""}
