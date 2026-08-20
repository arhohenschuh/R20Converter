"""Schema-conformance tests for emitted dnd5e ``system`` dicts.

The rest of the suite asserts the shapes the emitter produces, which is why
B027-B042 were all invisible to 513 green tests: a field dnd5e does not declare
looks identical to a field it does, until Foundry drops it on load.

These tests assert the other direction. Every key set below is read out of the
dnd5e 5.3.3 source, cited per block, and the tests fail when the converter emits
something outside it. Adding a type here is cheap; the point is that the check
is mechanical rather than a reviewer noticing.
"""

import json

import pytest

import dnd5e
from entities.base import Entity
from entities.actors import Actor
from entities.items import (Item, ItemActivation, ItemBackpack, ItemEquipment,
                            ItemInventoryAttributes, ItemObject, ItemUses,
                            ItemSpellPreparation, ItemWeapon)

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

#: ``NPCData``/``CharacterData`` declare no synthetic bar attributes. Neither
#: declares ``spelldc`` (derived by ``prepareSpellcastingAbility``) nor
#: ``spellLevel`` (the NPC caster level lives at ``attributes.spell.level``).
RETIRED_ACTOR_ATTRIBUTES = {"bar1", "bar2", "spelldc", "spellLevel"}

#: ``module/data/actor/templates/creature.mjs`` spells MappingField. ``max`` is
#: derived from progression, so an emitted one is dropped.
SPELL_SLOT_FIELDS = {"value", "override"}


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


class SlotActor(Actor):
    """An actor driven by canned slot attributes and NPC traits."""

    def __init__(self, npc=True, attributes=None, traits=None, export_as_module=False):
        self._shaped = False
        self._npc = npc
        self._attributes = attributes or {}
        self._traits = traits or {}
        self._export_as_module = export_as_module
        self.warnings = []

    def isNPC(self):
        return self._npc

    def logWarning(self, msg):
        self.warnings.append(msg)

    def getArgument(self, name, default=None):
        if name == "export_as_module":
            return self._export_as_module
        return default

    def getRepeatingAttributes(self, name):
        return self._traits if name == "npctrait" else {}

    def getAttribute(self, name, default=None, from_dict=None):
        source = from_dict if from_dict is not None else self._attributes
        return (source.get(name, default), None, None)


def _slots(**levels):
    # The sheet stores these as strings; both fields are NumberFields.
    attributes = {}
    for key, (total, remaining) in levels.items():
        level = int(key[-1])
        attributes["lvl%d_slots_total" % level] = str(total)
        attributes["lvl%d_slots_expended" % level] = str(remaining)
    return attributes


class TestSpellSlotShape(object):
    """B030: every leveled NPC caster arrived with no slots at all."""

    def test_entry_declares_only_schema_fields(self):
        spells = SlotActor(attributes=_slots(l3=(4, 2))).createActorSpells()
        assert set(spells["spell3"]) == SPELL_SLOT_FIELDS

    def test_no_level_emits_a_derived_max(self):
        # `max` is computed from progression; an emitted one is dropped, which
        # is why the sheet showed zero slots however many the statblock printed.
        spells = SlotActor(attributes=_slots(l1=(4, 4))).createActorSpells()
        assert all("max" not in entry for entry in spells.values())

    def test_cantrip_level_is_not_a_slot_level(self):
        # CreatureTemplate._spellLevels filters "0" out.
        assert "spell0" not in SlotActor().createActorSpells()

    def test_npc_slots_are_pinned_with_an_override(self):
        spells = SlotActor(attributes=_slots(l3=(4, 2))).createActorSpells()
        assert spells["spell3"]["override"] == 4
        assert spells["spell3"]["value"] == 2

    def test_module_npc_slots_start_at_full_capacity(self):
        spells = SlotActor(attributes=_slots(l3=(4, 2)),
                           export_as_module=True).createActorSpells()
        assert spells["spell3"] == {"value": 4, "override": 4}

    def test_world_npc_slots_preserve_current_availability(self):
        spells = SlotActor(attributes=_slots(l3=(4, 2)),
                           export_as_module=False).createActorSpells()
        assert spells["spell3"] == {"value": 2, "override": 4}

    def test_module_npc_without_printed_slots_uses_caster_progression(self):
        traits = {"t1": {"name": "Spellcasting",
                          "description": "The mage is a 5th-level spellcaster."}}
        spells = SlotActor(traits=traits, export_as_module=True).createActorSpells()
        assert [spells["spell%d" % level]["value"] for level in range(1, 4)] == [4, 3, 2]
        assert all(spells["spell%d" % level]["override"] is None
                   for level in range(1, 4))

    def test_remaining_above_capacity_is_clamped_and_reported(self):
        actor = SlotActor(attributes=_slots(l3=(2, 4)))
        spells = actor.createActorSpells()
        assert spells["spell3"] == {"value": 2, "override": 2}
        assert actor.warnings == ["Level 3 spell slots report 4 remaining from capacity 2; clamped"]

    def test_slots_are_numbers_not_sheet_strings(self):
        # Both are NumberFields. Foundry would cast "4", but leaning on that is
        # the habit ADR-008 exists to break -- and it hides real junk values.
        spells = SlotActor(attributes=_slots(l3=(4, 2))).createActorSpells()
        assert isinstance(spells["spell3"]["value"], int)
        assert isinstance(spells["spell3"]["override"], int)

    def test_unparseable_slot_count_becomes_zero_not_a_string(self):
        actor = SlotActor(attributes={"lvl1_slots_total": "", "lvl1_slots_expended": ""})
        entry = actor.createActorSpells()["spell1"]
        assert entry["value"] == 0
        assert entry["override"] is None

    def test_empty_level_keeps_progression_in_charge(self):
        spells = SlotActor(attributes=_slots(l3=(4, 2))).createActorSpells()
        assert spells["spell9"]["override"] is None

    def test_character_slots_come_from_class_progression(self):
        # A PC's classes are emitted and authoritative; pinning an override
        # would freeze the slots against level-ups.
        spells = SlotActor(npc=False, attributes=_slots(l3=(4, 2))).createActorSpells()
        assert spells["spell3"]["override"] is None
        assert spells["spell3"]["value"] == 2


class TestNPCCasterLevel(object):
    """B030: `attributes.spell.level` is what NPC slot progression reads."""

    def _actor(self, description):
        return SlotActor(traits={"t1": {"name": "Spellcasting",
                                        "description": description}})

    def test_level_is_read_from_the_spellcasting_trait(self):
        actor = self._actor("The archmage is an 18th-level spellcaster.")
        assert actor.getNPCCasterLevel() == 18

    @pytest.mark.parametrize("text,expected", [
        ("is a 1st-level spellcaster", 1),
        ("is a 2nd-level spellcaster", 2),
        ("is a 3rd-level spellcaster", 3),
        ("is a 9th level spellcaster", 9),
        ("is a 4-level spellcaster", 4),
    ])
    def test_every_ordinal_form_parses(self, text, expected):
        assert self._actor(text).getNPCCasterLevel() == expected

    def test_a_non_caster_reports_zero(self):
        assert self._actor("Keen Smell. Advantage on Perception.").getNPCCasterLevel() == 0


class TestInnateUses(object):
    """B036: `(\\d)` captured one digit, so "10/day" became 1 use, no recovery."""

    @pytest.mark.parametrize("text,count,period", [
        ("3/day each", 3, ItemUses.PER_DAY),
        ("10/day", 10, ItemUses.PER_DAY),
        ("12/day each", 12, ItemUses.PER_DAY),
        ("1/short rest", 1, ItemUses.PER_SHORT_REST),
        ("2/long rest", 2, ItemUses.PER_LONG_REST),
    ])
    def test_count_and_period_survive(self, text, count, period):
        assert Actor.parseInnateUses(text) == (count, period)

    def test_two_digit_count_keeps_its_period(self):
        # The regression: the period group failed against the second digit, so
        # the use never came back on a rest.
        assert Actor.parseInnateUses("10/day")[1] == ItemUses.PER_DAY

    def test_at_will_has_no_count(self):
        assert Actor.parseInnateUses("at will") == (None, "")


class CadenceActor(Actor):
    def __init__(self, drop_data="", spells=None, traits=None):
        self._shaped = False
        self._attributes = {"kingdom_drop_data": (drop_data, "", "drop")}
        self._repeating = {
            "spell-1": spells or {},
            "spell-2": {},
            "spell-3": {},
            "spell-4": {},
            "spell-cantrip": {},
            "npctrait": traits or {},
        }


def cadence_spell(name, identifier="spell-row"):
    return {"spellname": (name, "", identifier)}


def cadence_trait(name, description, identifier="trait-row"):
    return {"name": (name, "", identifier),
            "description": (description, "", identifier + "-description")}


class TestSourceInnateCadence(object):
    def test_structured_data_spells_is_authoritative(self):
        drop_data = json.dumps({"data-Spells": json.dumps({
            "spells": {"at-will": ["mage hand"], "2/day": ["darkness"]},
        })})
        actor = CadenceActor(drop_data, {
            "mage": cadence_spell("Mage Hand", "mage"),
            "dark": cadence_spell("Darkness", "dark"),
        })
        actor._repeating["spell-cantrip"] = {"mage": actor._repeating["spell-1"].pop("mage")}
        actor._repeating["spell-2"] = {"dark": actor._repeating["spell-1"].pop("dark")}
        assert actor.inferInnateCadence() == {
            ("mage hand", 0): "at will",
            ("darkness", 2): "2/day",
        }

    def test_trait_list_and_innately_cast_clause_are_parsed(self):
        actor = CadenceActor(spells={
            "animal": cadence_spell("Animal Friendship", "animal"),
            "suggest": cadence_spell("Suggestion", "suggest"),
            "misty": cadence_spell("Misty Step", "misty"),
        }, traits={
            "list": cadence_trait("Innate Spellcasting",
                "At will: animal friendship (snakes only)\n3/day: suggestion"),
            "single": cadence_trait("Innate Spellcasting",
                "The king can innately cast misty step at will, requiring no components."),
        })
        actor._repeating["spell-2"] = {
            "suggest": actor._repeating["spell-1"].pop("suggest"),
            "misty": actor._repeating["spell-1"].pop("misty"),
        }
        assert actor.inferInnateCadence() == {
            ("animal friendship", 1): "at will",
            ("suggestion", 2): "3/day",
            ("misty step", 2): "at will",
        }

    def test_named_item_trait_with_next_dawn_is_one_per_day(self):
        actor = CadenceActor(spells={
            "ray": cadence_spell("Scorching Ray", "ray"),
        }, traits={
            "circlet": cadence_trait("Circlet of Blasting",
                "The king can use an action to cast the scorching ray spell with it. "
                "The circlet can't be used this way again until the next dawn."),
        })
        actor._repeating["spell-2"] = actor._repeating.pop("spell-1")
        assert actor.inferInnateCadence() == {
            ("scorching ray", 2): "1/day",
        }

    def test_duplicate_emitted_spell_rows_make_cadence_ambiguous(self):
        actor = CadenceActor(spells={
            "first": cadence_spell("Suggestion", "first"),
            "second": cadence_spell("Suggestion", "second"),
        }, traits={
            "list": cadence_trait("Innate Spellcasting", "3/day: suggestion"),
        })
        with pytest.raises(ValueError, match="matches 2 emitted rows"):
            actor.inferInnateCadence()

    def test_structured_and_trait_cadence_contradiction_is_rejected(self):
        drop_data = json.dumps({"data-Spells": json.dumps({
            "spells": {"2/day": ["darkness"]},
        })})
        actor = CadenceActor(drop_data, {
            "dark": cadence_spell("Darkness", "dark"),
        }, {
            "list": cadence_trait("Innate Spellcasting", "3/day: darkness"),
        })
        with pytest.raises(ValueError, match="contradictory cadence"):
            actor.inferInnateCadence()

    def test_ordinary_prepared_spell_has_no_inferred_cadence(self):
        actor = CadenceActor(spells={"shield": cadence_spell("Shield", "shield")})
        assert actor.inferInnateCadence() == {}


class TestRitualOnlyPreparation(object):
    def test_at_will_uses_native_casting_method(self):
        preparation = ItemSpellPreparation(ItemSpellPreparation.ALWAYS_AVAILABLE, True).getDict()
        assert preparation == {"method": "atwill", "prepared": 1}

    def test_explicit_ritual_only_uses_ritual_method(self):
        preparation = ItemSpellPreparation("ritual", True).getDict()
        assert preparation == {"method": "ritual", "prepared": 1}

    def test_ritual_capable_class_spell_keeps_slot_method(self):
        preparation = ItemSpellPreparation(ItemSpellPreparation.PREPARED_SPELL, True).getDict()
        assert preparation == {"method": "spell", "prepared": 1}


class TestRecoveryPeriods(object):
    """B039: "charges" is a consumption type in 5.x, not a recovery period."""

    def test_charges_is_not_a_recovery_period(self):
        assert "charges" not in dnd5e.RECOVERY_PERIODS

    def test_every_period_is_a_configured_key(self):
        # CONFIG.DND5E.limitedUsePeriods plus the special `recharge`.
        assert set(dnd5e.RECOVERY_PERIODS) <= {
            "lr", "sr", "day", "dawn", "dusk", "initiative", "turnStart",
            "turnEnd", "turn", "recharge"}

    def test_legacy_charges_yields_no_recovery_rule(self):
        uses = dnd5e.usesFromLegacy(2, 3, ItemUses.PER_CHARGES)
        assert uses["recovery"] == []

    def test_recovery_rejects_an_unconfigured_period(self):
        assert dnd5e.recovery("charges") is None


class TestCreatureType(object):
    """B041: the whole phrase was stored where a config key was expected."""

    def test_parenthetical_becomes_the_subtype(self):
        assert dnd5e.creatureType("humanoid (goblinoid)") == {
            "value": "humanoid", "subtype": "goblinoid", "swarm": "", "custom": ""}

    def test_plain_type_needs_no_splitting(self):
        assert dnd5e.creatureType("dragon")["value"] == "dragon"

    def test_value_is_always_a_configured_key(self):
        for text in ["Humanoid (Any Race)", "beast", "swarm of Tiny beasts"]:
            value = dnd5e.creatureType(text)["value"]
            assert value in dnd5e.CREATURE_TYPES, "%r -> %r" % (text, value)

    def test_swarm_records_the_size_key(self):
        parsed = dnd5e.creatureType("swarm of Tiny beasts")
        assert parsed["swarm"] == "tiny"
        assert parsed["value"] == "beast"

    def test_unknown_type_goes_to_custom_not_value(self):
        parsed = dnd5e.creatureType("myconid")
        assert parsed["value"] == ""
        assert parsed["custom"] == "myconid"

    def test_field_always_has_the_four_declared_keys(self):
        assert set(dnd5e.creatureType("")) == {"value", "subtype", "swarm", "custom"}


class TestContainerShape(object):
    """B040: `backpack` triggers a source migration; capacity was 1.5.6-shaped."""

    def _container(self, tmp_path, backpack):
        return Item.createItemBackpack(
            FakeDatabase(str(tmp_path)), None, "Bag of Holding", "",
            ItemInventoryAttributes(weight=15, price=4000), backpack)

    def test_type_is_container_not_backpack(self, tmp_path):
        # Item5e._initializeSource rewrites `backpack` and sets
        # persistSourceMigration, queueing the document for a rewrite.
        item = self._container(tmp_path, ItemBackpack())
        assert item.entity["type"] == "container"

    def test_weight_capacity_uses_the_declared_shape(self, tmp_path):
        capacity = self._container(
            tmp_path, ItemBackpack(ItemBackpack.WEIGHT, 500)).entity["system"]["capacity"]
        assert capacity["weight"] == dnd5e.weightData(500)

    def test_item_capacity_becomes_a_count(self, tmp_path):
        capacity = self._container(
            tmp_path, ItemBackpack(ItemBackpack.ITEMS, 12)).entity["system"]["capacity"]
        assert capacity["count"] == 12

    def test_legacy_capacity_keys_are_gone(self, tmp_path):
        capacity = self._container(
            tmp_path, ItemBackpack(ItemBackpack.WEIGHT, 500)).entity["system"]["capacity"]
        assert not (set(capacity) & {"type", "value", "weightless"})

    def test_weightless_becomes_a_property(self, tmp_path):
        system = self._container(
            tmp_path, ItemBackpack(ItemBackpack.WEIGHT, 500, weightless=True)).entity["system"]
        assert "weightlessContents" in system["properties"]

    def test_quantity_is_clamped_to_one(self, tmp_path):
        # ContainerData declares quantity {min: 1, max: 1}.
        system = self._container(tmp_path, ItemBackpack()).entity["system"]
        assert system["quantity"] == 1


class TestLimitedUseConsumption(object):
    """B029: activating a limited-use item never spent a use."""

    def _feat(self, tmp_path, uses=None):
        activation = ItemActivation(ItemActivation.ACTION, 1, uses=uses)
        return Item.createItemFeat(
            FakeDatabase(str(tmp_path)), None, "Breath Weapon", "",
            activation, None, None, ability_mods={"str": 3})

    def _activity(self, item):
        return next(iter(item.entity["system"]["activities"].values()))

    def test_activity_consumes_the_items_uses(self, tmp_path):
        activity = self._activity(self._feat(tmp_path, ItemUses(2, 2, "day")))
        targets = activity["consumption"]["targets"]
        assert len(targets) == 1
        assert targets[0]["type"] == dnd5e.CONSUMPTION_ITEM_USES

    def test_consumption_target_declares_only_schema_fields(self, tmp_path):
        activity = self._activity(self._feat(tmp_path, ItemUses(2, 2, "day")))
        target = activity["consumption"]["targets"][0]
        assert set(target) == {"type", "target", "value", "scaling"}
        assert target["value"] == "1"

    def test_the_uses_pool_is_not_duplicated_onto_the_activity(self, tmp_path):
        # ActivitiesTemplate puts the pool on the item root; a copy here is a
        # second pool the sheet renders next to the real one.
        item = self._feat(tmp_path, ItemUses(2, 2, "day"))
        assert item.entity["system"]["uses"]["max"] == "2"
        assert "max" not in self._activity(item)["uses"]

    def test_an_unlimited_item_consumes_nothing(self, tmp_path):
        activity = self._activity(self._feat(tmp_path))
        assert activity["consumption"]["targets"] == []


class TestShortHexColour(object):
    """B042: CSS shorthand repeats the nibble; x16 darkens every short colour."""

    @pytest.mark.parametrize("short,expanded", [
        ("#fff", "#ffffff"),
        ("#000", "#000000"),
        ("#abc", "#aabbcc"),
        ("#f00", "#ff0000"),
    ])
    def test_shorthand_expands_by_repetition(self, short, expanded):
        assert Entity.color(short) == expanded

    def test_alpha_nibble_is_ignored_not_misread(self):
        assert Entity.color("#abcd") == "#aabbcc"

    def test_long_form_is_unchanged(self):
        assert Entity.color("#1a2b3c") == "#1a2b3c"
