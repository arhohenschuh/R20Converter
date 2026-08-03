"""Schema-conformance tests for emitted dnd5e ``system`` dicts.

The rest of the suite asserts the shapes the emitter produces, which is why
B027-B042 were all invisible to 513 green tests: a field dnd5e does not declare
looks identical to a field it does, until Foundry drops it on load.

These tests assert the other direction. Every key set below is read out of the
dnd5e 5.3.3 source, cited per block, and the tests fail when the converter emits
something outside it. Adding a type here is cheap; the point is that the check
is mechanical rather than a reviewer noticing.
"""

import pytest

import dnd5e
from entities.actors import Actor
from entities.items import (Item, ItemEquipment, ItemInventoryAttributes,
                            ItemObject, ItemWeapon)

from conftest import FakeDatabase


#: ``module/data/item/templates/physical-item.mjs`` defineSchema().
PHYSICAL_ITEM_FIELDS = {"container", "quantity", "weight", "price", "rarity"}

#: ``module/data/item/templates/equippable-item.mjs`` defineSchema().
EQUIPPABLE_ITEM_FIELDS = {"attunement", "attuned", "equipped"}

#: Fields removed between 1.5.6 and 5.x. Emitting any of these is silent loss.
RETIRED_ITEM_FIELDS = {
    "weaponType", "armorType", "consumableType", "toolType", "baseItem",
    "actionType", "attackBonus", "chatFlavor", "critical", "formula",
    "speed", "stealth", "hp", "consume", "save", "subclass", "saves", "skills",
}

#: ``NPCData``/``CharacterData`` declare no synthetic bar attributes.
RETIRED_ACTOR_ATTRIBUTES = {"bar1", "bar2"}


def physicalItems(database):
    """One instance of every factory that produces a physical item."""
    attributes = ItemInventoryAttributes(weight=3, price=25, attunement=1)
    return {
        "loot": Item.createItemLoot(database, None, "Rope", "", attributes),
        "weapon": Item.createItemWeapon(database, None, "Longsword", "", None,
                                        None, ItemInventoryAttributes(weight=3, price=15),
                                        ItemWeapon()),
        "equipment": Item.createItemEquipment(database, None, "Chain Mail", "", None,
                                              None, ItemInventoryAttributes(weight=55, price=75),
                                              ItemEquipment(ItemEquipment.HEAVY_ARMOR)),
    }


class TestPhysicalItemShape(object):
    """B028: a bare number fails SchemaField validation and is reset on load."""

    @pytest.fixture
    def items(self, tmp_path):
        return physicalItems(FakeDatabase(str(tmp_path)))

    def test_weight_is_an_object_not_a_number(self, items):
        for name, item in items.items():
            weight = item.entity["system"]["weight"]
            assert isinstance(weight, dict), "%s emitted a bare weight" % name
            assert set(weight) == {"value", "units"}

    def test_price_is_an_object_not_a_number(self, items):
        for name, item in items.items():
            price = item.entity["system"]["price"]
            assert isinstance(price, dict), "%s emitted a bare price" % name
            assert set(price) == {"value", "denomination"}

    def test_weight_and_price_keep_their_values(self, items):
        assert items["loot"].entity["system"]["weight"]["value"] == 3
        assert items["loot"].entity["system"]["price"]["value"] == 25

    def test_units_are_populated(self, items):
        system = items["loot"].entity["system"]
        assert system["weight"]["units"] == dnd5e.DEFAULT_WEIGHT_UNITS
        assert system["price"]["denomination"] == dnd5e.DEFAULT_PRICE_DENOMINATION

    def test_attunement_is_a_string(self, items):
        # 1.5.6 wrote 0/1/2; a StringField casts those to junk like "0".
        attunement = items["loot"].entity["system"]["attunement"]
        assert isinstance(attunement, str)
        assert attunement in {dnd5e.ATTUNEMENT_NONE, dnd5e.ATTUNEMENT_REQUIRED,
                              dnd5e.ATTUNEMENT_OPTIONAL}

    @pytest.mark.parametrize("legacy,expected", [
        (0, dnd5e.ATTUNEMENT_NONE),
        (1, dnd5e.ATTUNEMENT_REQUIRED),
        (2, dnd5e.ATTUNEMENT_REQUIRED),
    ])
    def test_legacy_attunement_is_mapped(self, legacy, expected):
        assert dnd5e.attunement(legacy) == expected


class TestNoRetiredFields(object):
    """The whole B028/B032/B033/B037/B038 class in one assertion."""

    def test_no_physical_item_emits_a_retired_field(self, tmp_path):
        for name, item in physicalItems(FakeDatabase(str(tmp_path))).items():
            emitted = set(item.entity["system"])
            assert not (emitted & RETIRED_ITEM_FIELDS), (
                "%s emits retired field(s) %s"
                % (name, sorted(emitted & RETIRED_ITEM_FIELDS)))

    def test_weapons_carry_no_armor_or_hp_block(self, tmp_path):
        # B033: ItemObject stamped armor.value 10 and an hp block onto weapons.
        system = physicalItems(FakeDatabase(str(tmp_path)))["weapon"].entity["system"]
        assert "hp" not in system
        assert "armor" not in system

    def test_item_object_emits_nothing(self):
        assert ItemObject().getDict() == {}


class TestArmorDexCap(object):
    """B033: ``dex`` is nullable -- None is uncapped, 0 is a real cap of +0."""

    @pytest.mark.parametrize("armor_type,expected", [
        (ItemEquipment.LIGHT_ARMOR, None),
        (ItemEquipment.MEDIUM_ARMOR, 2),
        (ItemEquipment.HEAVY_ARMOR, 0),
    ])
    def test_dex_cap_follows_armor_category(self, armor_type, expected):
        assert ItemEquipment(armor_type).getDict()["armor"]["dex"] == expected

    def test_stealth_is_a_property_not_a_boolean(self):
        equipment = ItemEquipment(ItemEquipment.HEAVY_ARMOR, stealth=True).getDict()
        assert "stealth" not in equipment
        assert dnd5e.STEALTH_DISADVANTAGE in equipment["properties"]

    def test_no_stealth_means_no_property(self):
        assert ItemEquipment(ItemEquipment.LIGHT_ARMOR).getDict()["properties"] == []


#: ``module/data/actor/templates/creature.mjs`` skills MappingField(RollConfigField).
SKILL_FIELDS = {"value", "ability", "bonuses", "roll"}

#: Same file, tools MappingField(RollConfigField).
TOOL_FIELDS = {"value", "ability", "bonuses"}

#: Removed from the skill entry: mod and passive are derived, bonus is a formula.
RETIRED_SKILL_FIELDS = {"mod", "passive", "bonus"}


class ShapedActor(Actor):
    """A Shaped-sheet actor driven by canned repeating attributes.

    The Shaped branch is only reachable through ``_shaped``, which is why B038
    survived F022 -- nothing exercised it.
    """

    def __init__(self, skills=None, tools=None, proficiencies=None):
        self._shaped = True
        self._skills = skills or {}
        self._tools = tools or {}
        self._proficiencies = proficiencies or ""
        self._actor_abilities = {"dex": {}}
        self.warnings = []

    def getName(self):
        return "Shaped Test Actor"

    def logWarning(self, msg):
        self.warnings.append(msg)

    def isNPC(self):
        return False

    def getProficiencyBonus(self):
        return 2

    def abilityDerived(self, ability, key):
        return 3

    def getRepeatingAttributes(self, name):
        if name == "skill":
            return self._skills
        if name == "tool":
            return self._tools
        return {}

    def getAttribute(self, name, default=None, from_dict=None):
        source = from_dict if from_dict is not None else {"proficiencies": self._proficiencies}
        return (source.get(name, default), None, None)

    def getAttributeInt(self, name, default=0, from_dict=None):
        source = from_dict or {}
        try:
            return int(source.get(name, default))
        except (TypeError, ValueError):
            return default


class TestShapedSkillShape(object):
    """B038: the Shaped branch still emitted the shape F022 removed."""

    def makeActor(self, **skill):
        entry = {"storage_name": "stealth", "name": "Stealth", "ability": "dexterity",
                 "ability_key": "dex", "total_with_sign": 7}
        entry.update(skill)
        return ShapedActor(skills={"s1": entry})

    def test_entry_declares_only_schema_fields(self):
        skill = self.makeActor().createActorSkills()["ste"]
        assert set(skill) == SKILL_FIELDS

    def test_retired_fields_are_gone(self):
        skill = self.makeActor().createActorSkills()["ste"]
        assert not (set(skill) & RETIRED_SKILL_FIELDS)

    def test_bonuses_are_formula_strings(self):
        bonuses = self.makeActor().createActorSkills()["ste"]["bonuses"]
        assert set(bonuses) == {"check", "passive"}
        assert all(isinstance(v, str) for v in bonuses.values())

    def test_bonus_sign_matches_the_standard_branch(self):
        # mod 9, ability mod 3, prof 2 -> expertise (value 2), residual +2.
        # The Shaped branch computed this the other way round and produced -2.
        skill = self.makeActor(total_with_sign=9).createActorSkills()["ste"]
        assert not skill["bonuses"]["check"].startswith("-")

    def test_unmapped_skill_is_reported_not_silently_emitted(self):
        # 5.x `skills` only accepts configured keys, so an invented one is
        # deleted on load without a warning.
        actor = ShapedActor(skills={"s1": {"storage_name": "basketweaving",
                                           "name": "Basketweaving",
                                           "ability": "dexterity",
                                           "ability_key": "dex",
                                           "total_with_sign": 4}})
        assert actor.createActorSkills().get("basketweaving") is None
        assert any("Basketweaving" in w for w in actor.warnings)


class TestActorToolShape(object):
    """B037: 5.x reads system.tools; traits.toolProf survives only via a shim."""

    def test_recognised_tool_becomes_a_tools_entry(self):
        actor = ShapedActor(tools={"t1": {"toolname": "Thieves' Tools"}})
        tools = actor.createActorTools()
        assert set(tools) == {"thief"}
        assert set(tools["thief"]) == TOOL_FIELDS

    def test_entry_matches_what_the_dnd5e_shim_writes(self):
        # #migrateToolData writes exactly {value: 1, ability: "int",
        # bonuses: {check: ""}}; emitting it directly is what drops the shim.
        entry = ShapedActor(tools={"t1": {"toolname": "Herbalism Kit"}}).createActorTools()["herb"]
        assert entry == {"value": 1, "ability": "int", "bonuses": {"check": ""}}

    def test_unrecognised_tool_is_reported(self):
        actor = ShapedActor(tools={"t1": {"toolname": "Tinker's Whatsit"}})
        assert actor.createActorTools() == {}
        assert any("Tinker's Whatsit" in w for w in actor.warnings)

    def test_traits_no_longer_carry_toolprof(self):
        actor = ShapedActor(tools={"t1": {"toolname": "Thieves' Tools"}})
        assert "toolProf" not in actor.createActorTraits()
