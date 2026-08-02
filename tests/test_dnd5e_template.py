"""Regression tests for the activated-effect template and spell shapes.

These close B006-B010. Every one of them describes a field dnd5e 5.3.3 actually
reads, quoted from ``module/data/shared/*-field.mjs`` and
``module/data/item/spell.mjs`` — not from the shape the converter happens to
produce. A test written the other way around is what let B001 through.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import dnd5e  # noqa: E402
from entities.items import (  # noqa: E402
    Item, ItemActivation, ItemAttack, ItemDamage, ItemDuration,
    ItemFeatRecharge, ItemRange, ItemSpellComponents, ItemSpellPreparation,
    ItemSpellScaling, ItemTarget, ItemUses,
)

from conftest import FakeDatabase  # noqa: E402


@pytest.fixture
def db(tmp_path):
    return FakeDatabase(str(tmp_path), {})


# ---------------------------------------------------------------------------
# B009 — the shared activated-effect template
# ---------------------------------------------------------------------------

class TestActivation(object):
    def test_scalar_is_named_value_not_cost(self):
        """v1.5.6 called it ``cost``; 5.x reads ``value`` and drops ``cost``."""
        data = dnd5e.activationData("action", 3, "on a hit")
        assert data == {"type": "action", "value": 3, "condition": "on a hit"}
        assert "cost" not in data

    @pytest.mark.parametrize("legacy", ["none", "", "nonsense"])
    def test_types_absent_from_5x_become_blank(self, legacy):
        """``none`` is not in ``activityActivationTypes``; ``special`` is."""
        assert dnd5e.activationData(legacy)["type"] == ""

    @pytest.mark.parametrize("valid", [
        # Copied from CONFIG.DND5E.activityActivationTypes in 5.3.3 rather than
        # read back out of ACTIVATION_TYPES, so an omission from our own tuple
        # is a failure rather than an agreement with itself.
        "action", "bonus", "reaction", "minute", "hour", "day", "longRest",
        "shortRest", "encounter", "turnStart", "turnEnd", "legendary", "mythic",
        "lair", "crew", "special",
    ])
    def test_every_valid_type_survives(self, valid):
        assert dnd5e.activationData(valid)["type"] == valid

    def test_zero_cost_is_not_written_as_zero(self):
        """``value`` is a NumberField with ``min: 0``; a real 0 means 0 actions."""
        assert dnd5e.activationData("action", 0)["value"] is None


class TestRange(object):
    def test_long_is_gone(self):
        assert "long" not in dnd5e.rangeData(30, "ft")

    def test_distance_units_keep_their_value(self):
        assert dnd5e.rangeData(120, "ft") == {
            "value": "120", "units": "ft", "special": ""}

    @pytest.mark.parametrize("units", ["self", "touch", "spec", "any"])
    def test_non_scalar_units_carry_no_value(self, units):
        """dnd5e nulls ``range.value`` unless the unit is a movement unit."""
        assert dnd5e.rangeData(5, units)["value"] == ""

    @pytest.mark.parametrize("bad", ["none", "", "feet", None])
    def test_invalid_units_resolve_to_self(self, bad):
        """``units`` is ``blank: false``; an invalid value silently resets."""
        assert dnd5e.rangeData(None, bad)["units"] == "self"

    def test_legacy_none_is_not_passed_through(self):
        assert dnd5e.rangeData(None, "none")["units"] != "none"


class TestDuration(object):
    @pytest.mark.parametrize("bad", ["", None, "forever"])
    def test_invalid_units_resolve_to_instantaneous(self, bad):
        assert dnd5e.durationData(1, bad)["units"] == "inst"

    def test_scalar_period_keeps_its_value(self):
        assert dnd5e.durationData(10, "minute") == {
            "value": "10", "units": "minute", "special": ""}

    def test_permanent_carries_no_value(self):
        assert dnd5e.durationData(1, "perm")["value"] == ""


class TestTarget(object):
    def test_flat_shape_is_replaced_by_template_and_affects(self):
        data = dnd5e.targetData("creature", 1, None, "ft")
        assert set(data) == {"template", "affects"}
        assert "value" not in data and "type" not in data

    @pytest.mark.parametrize("area", list(dnd5e.AREA_TARGET_TYPES))
    def test_areas_land_in_template(self, area):
        data = dnd5e.targetData(area, 20, 5, "ft")
        assert data["template"]["type"] == area
        assert data["template"]["size"] == "20"
        assert data["affects"]["type"] == ""

    @pytest.mark.parametrize("individual", list(dnd5e.INDIVIDUAL_TARGET_TYPES))
    def test_individuals_land_in_affects(self, individual):
        data = dnd5e.targetData(individual, 2)
        assert data["affects"]["type"] == individual
        assert data["affects"]["count"] == "2"
        assert data["template"]["type"] == ""

    def test_unknown_type_is_not_passed_through_as_an_enum(self):
        """An invalid enum value fails validation for the whole document."""
        data = dnd5e.targetData("wibble")
        assert data["template"]["type"] == ""
        assert data["affects"]["type"] == ""
        assert data["affects"]["special"] == "wibble"

    def test_no_target_is_empty_on_both_sides(self):
        data = dnd5e.targetData("")
        assert data["template"]["type"] == ""
        assert data["affects"]["type"] == ""


class TestUses(object):
    def test_shape_is_spent_max_recovery(self):
        data = dnd5e.usesData(1, 3, [dnd5e.recovery("lr")])
        assert set(data) == {"spent", "max", "recovery"}
        assert "value" not in data and "per" not in data

    def test_remaining_uses_are_converted_to_spent(self):
        """v1.5.6 stored uses *remaining*; 5.x stores uses *spent*."""
        assert dnd5e.usesFromLegacy(value=1, maximum=3, per="day")["spent"] == 2

    def test_full_charges_are_zero_spent(self):
        assert dnd5e.usesFromLegacy(value=3, maximum=3, per="day")["spent"] == 0

    def test_max_is_a_formula_string(self):
        assert dnd5e.usesFromLegacy(0, 5, "lr")["max"] == "5"

    def test_period_becomes_a_recovery_rule(self):
        data = dnd5e.usesFromLegacy(1, 1, "lr")
        assert data["recovery"] == [
            {"period": "lr", "type": "recoverAll", "formula": ""}]

    def test_unlimited_item_has_no_recovery(self):
        assert dnd5e.usesFromLegacy(0, 0, "")["recovery"] == []

    def test_unknown_period_is_dropped_rather_than_invented(self):
        assert dnd5e.usesFromLegacy(1, 1, "fortnightly")["recovery"] == []


class TestRecharge(object):
    def test_recharge_is_a_recovery_rule_not_a_root_field(self):
        """5.x has no ``system.recharge``."""
        data = ItemFeatRecharge(5, charged=True).getDict()
        assert "recharge" not in data
        assert data["uses"]["recovery"] == [
            {"period": "recharge", "type": "recoverAll", "formula": "5"}]

    def test_uncharged_feature_starts_spent(self):
        assert ItemFeatRecharge(6, charged=False).getDict()["uses"]["spent"] == 1

    def test_no_recharge_leaves_uses_alone(self):
        assert ItemFeatRecharge(0).getDict() == {}


# ---------------------------------------------------------------------------
# B006 — spell-specific fields
# ---------------------------------------------------------------------------

class TestSpellShapes(object):
    def test_components_become_properties(self):
        data = ItemSpellComponents(v=True, s=True, m=False,
                                   concentration=True, ritual=False).getDict()
        assert "components" not in data
        assert sorted(data["properties"]) == ["concentration", "somatic", "vocal"]

    def test_properties_never_contain_unknown_keys(self):
        for key in ItemSpellComponents(v=True, s=True, m=True,
                                       concentration=True, ritual=True
                                       ).getDict()["properties"]:
            assert key in dnd5e.SPELL_PROPERTIES

    def test_materials_survive(self):
        data = ItemSpellComponents(m=True, materials="a pinch of soot",
                                   cost=10).getDict()
        assert data["materials"]["value"] == "a pinch of soot"
        assert data["materials"]["cost"] == 10

    def test_scaling_is_not_a_system_field(self):
        """``system.scaling`` does not exist in 5.3.3 SpellData."""
        assert ItemSpellScaling("level", "1d8").getDict() == {}

    def test_preparation_becomes_method_and_numeric_prepared(self):
        data = ItemSpellPreparation("prepared", True).getDict()
        assert data == {"method": "spell", "prepared": dnd5e.SPELL_PREPARED}
        assert "preparation" not in data

    def test_always_prepared_uses_state_two(self):
        assert ItemSpellPreparation("always", True).getDict() == {
            "method": "spell", "prepared": dnd5e.SPELL_ALWAYS_PREPARED}

    def test_innate_stays_innate_and_is_castable(self):
        data = ItemSpellPreparation("innate", False).getDict()
        assert data["method"] == "innate"
        assert data["prepared"] == dnd5e.SPELL_PREPARED

    def test_pact_stays_pact(self):
        assert ItemSpellPreparation("pact", True).getDict()["method"] == "pact"

    def test_method_is_always_a_known_spellcasting_key(self):
        for mode in ["prepared", "always", "innate", "pact", "", "garbage"]:
            method = ItemSpellPreparation(mode, True).getDict()["method"]
            assert method in dnd5e.SPELLCASTING_METHODS


class TestDamageScaling(object):
    def test_no_scaling_is_blank(self):
        assert dnd5e.damageScaling("none", "") == ("", 1, "")

    def test_level_scaling_becomes_whole(self):
        assert dnd5e.damageScaling("level", "2d6", denomination=8) == (
            "whole", 1, "2d6")

    def test_matching_denomination_becomes_a_die_count(self):
        """Mirrors ``transformDamagePartData``: same die -> number, not formula."""
        assert dnd5e.damageScaling("level", "2d8", denomination=8) == (
            "whole", 2, "")

    def test_cantrip_always_becomes_a_die_count(self):
        assert dnd5e.damageScaling("cantrip", "1d10", denomination=10) == (
            "whole", 1, "")


# ---------------------------------------------------------------------------
# B007 / B010 — activities
# ---------------------------------------------------------------------------

def _spell(db, name, attack=None, activation=None, scaling=None, **kwargs):
    return Item.createItemSpell(
        db, "spell-%s" % name, name, "", activation, attack,
        kwargs.pop("level", 1), "evo", None,
        ItemSpellPreparation("prepared", True), scaling, **kwargs)


class TestUtilityActivity(object):
    def test_activated_but_unrollable_spell_gets_a_utility_activity(self, db):
        """dnd5e's own migration defaults to ``utility``; without one there is
        no button on the sheet at all."""
        item = _spell(db, "Fog Cloud",
                      activation=ItemActivation(ItemActivation.ACTION, 1))
        activities = item.entity["system"]["activities"]
        assert len(activities) == 1
        assert next(iter(activities.values()))["type"] == "utility"

    def test_passive_trait_gets_no_activity(self, db):
        item = _spell(db, "Passive", activation=ItemActivation())
        assert item.entity["system"]["activities"] == {}

    def test_utility_activity_id_matches_its_key(self, db):
        item = _spell(db, "Blur", activation=ItemActivation(ItemActivation.ACTION, 1))
        for key, activity in item.entity["system"]["activities"].items():
            assert activity["_id"] == key
            assert len(key) == 16

    def test_a_rollable_spell_does_not_also_get_a_utility(self, db):
        attack = ItemAttack(type=ItemAttack.RANGED_SPELL, ability="int")
        attack.damages.damages.append(("2d6", "fire"))
        item = _spell(db, "Scorching Ray", attack=attack,
                      activation=ItemActivation(ItemActivation.ACTION, 1))
        types = [a["type"] for a in item.entity["system"]["activities"].values()]
        assert types == ["attack"]


class TestHealingActivity(object):
    def test_healing_amount_is_not_dropped(self, db):
        """B010: the heal activity was built without its healing formula."""
        attack = ItemAttack(type=ItemAttack.HEALING)
        attack.damages.damages.append(("1d8 + 3", "healing"))
        item = _spell(db, "Cure Wounds", attack=attack,
                      activation=ItemActivation(ItemActivation.ACTION, 1))
        activity = next(iter(item.entity["system"]["activities"].values()))
        assert activity["type"] == "heal"
        assert activity["healing"]["number"] == 1
        assert activity["healing"]["denomination"] == 8

    def test_healing_is_typed_as_healing(self, db):
        attack = ItemAttack(type=ItemAttack.HEALING)
        attack.damages.damages.append(("2d4", ""))
        item = _spell(db, "Healing Word", attack=attack,
                      activation=ItemActivation(ItemActivation.ACTION, 1))
        activity = next(iter(item.entity["system"]["activities"].values()))
        assert activity["healing"]["types"] == ["healing"]


# ---------------------------------------------------------------------------
# The invariant that matters: no legacy field reaches a document
# ---------------------------------------------------------------------------

LEGACY_SYSTEM_FIELDS = [
    "weaponType", "armorType", "consumableType", "toolType", "actionType",
    "attackBonus", "chatFlavor", "critical", "formula", "scaling", "ability",
    "components", "preparation", "consume", "recharge",
]


class TestNoLegacyFields(object):
    @pytest.mark.parametrize("field", LEGACY_SYSTEM_FIELDS)
    def test_spell_carries_no_legacy_field(self, db, field):
        attack = ItemAttack(type=ItemAttack.RANGED_SPELL, ability="int")
        attack.damages.damages.append(("1d10", "fire"))
        item = _spell(db, "Fire Bolt", attack=attack,
                      activation=ItemActivation(ItemActivation.ACTION, 1),
                      scaling=ItemSpellScaling("cantrip", "1d10"), level=0)
        assert field not in item.entity["system"]

    def test_spell_activation_has_no_cost_key(self, db):
        item = _spell(db, "Bless", activation=ItemActivation(ItemActivation.ACTION, 1))
        assert "cost" not in item.entity["system"]["activation"]

    def test_spell_uses_has_no_per_key(self, db):
        item = _spell(db, "Bless",
                      activation=ItemActivation(ItemActivation.ACTION, 1,
                                                uses=ItemUses(1, 1, "day")))
        assert "per" not in item.entity["system"]["uses"]
        assert "value" not in item.entity["system"]["uses"]

    def test_spell_target_has_no_flat_value(self, db):
        item = _spell(db, "Bless", activation=ItemActivation(
            ItemActivation.ACTION, 1,
            target=ItemTarget(ItemTarget.CREATURE, ItemRange(3))))
        assert "value" not in item.entity["system"]["target"]
        assert item.entity["system"]["target"]["affects"]["type"] == "creature"

    def test_cantrip_scaling_reaches_the_damage_part(self, db):
        attack = ItemAttack(type=ItemAttack.RANGED_SPELL, ability="int")
        attack.damages.damages.append(("1d10", "fire"))
        item = _spell(db, "Fire Bolt", attack=attack,
                      activation=ItemActivation(ItemActivation.ACTION, 1),
                      scaling=ItemSpellScaling("cantrip", "1d10"), level=0)
        activity = next(iter(item.entity["system"]["activities"].values()))
        part = activity["damage"]["parts"][0]
        assert part["scaling"]["mode"] == "whole"
        assert part["scaling"]["number"] == 1


# ---------------------------------------------------------------------------
# B012-B017 — findings from the R2 design review
# ---------------------------------------------------------------------------

def _weapon(db, name="Longsword", activation=None, **kwargs):
    from entities.items import ItemWeapon
    attack = ItemAttack(type=ItemAttack.MELEE_WEAPON, ability="str")
    attack.damages.damages.append(("1d8", "slashing"))
    return Item.createItemWeapon(db, "w-%s" % name, name, "", activation, attack,
                                 None, ItemWeapon(_type="martialM"),
                                 ability_mods={"str": 3}, **kwargs)


def _feat(db, name="Breath Weapon", attack=None, activation=None, recharge=None):
    return Item.createItemFeat(db, "f-%s" % name, name, "", activation,
                               attack, recharge, ability_mods={"str": 3})


class TestActivityCarriesItsOwnMetadata(object):
    """B013: only SpellData keeps activation/range/duration/target at the root.

    On every other item type those keys are not in the schema, so Foundry drops
    them and the activity keeps its defaults — a reaction becomes an action and
    a 120 ft attack reads "self".
    """

    def test_weapon_activation_reaches_the_activity(self, db):
        item = _weapon(db, activation=ItemActivation(ItemActivation.REACTION, 1))
        activity = next(iter(item.entity["system"]["activities"].values()))
        assert activity["activation"]["type"] == "reaction"
        assert activity["activation"]["override"] is True

    def test_weapon_does_not_keep_activation_at_the_root(self):
        """WeaponData has no `activation` field; emitting one is dead weight."""
        item_fields = ["activation", "target", "duration"]
        from entities.items import Item as _I
        data = _I.createStandardData(
            "", "", ItemActivation(ItemActivation.ACTION, 1), None,
            item_type="weapon", item_name="Longsword")
        for field in item_fields:
            assert field not in data, "%r is not in WeaponData" % field

    def test_weapon_keeps_uses_at_the_root(self):
        """ActivitiesTemplate does give every activatable item `uses`."""
        from entities.items import Item as _I
        data = _I.createStandardData(
            "", "", ItemActivation(ItemActivation.ACTION, 1,
                                   uses=ItemUses(2, 2, "day")),
            None, item_type="weapon", item_name="Longsword")
        assert data["uses"]["max"] == "2"

    def test_spell_keeps_activation_at_the_root_and_inherits(self, db):
        """SpellData does declare them, so the activity should not override."""
        item = _spell(db, "Bless",
                      activation=ItemActivation(ItemActivation.ACTION, 1))
        assert item.entity["system"]["activation"]["type"] == "action"
        activity = next(iter(item.entity["system"]["activities"].values()))
        assert activity["activation"]["override"] is False

    def test_feat_range_reaches_the_activity(self, db):
        attack = ItemAttack(type=ItemAttack.RANGED_WEAPON, ability="dex")
        attack.damages.damages.append(("2d6", "fire"))
        item = _feat(db, attack=attack, activation=ItemActivation(
            ItemActivation.ACTION, 1, range=ItemRange(120, None, "ft")))
        activity = next(iter(item.entity["system"]["activities"].values()))
        assert activity["range"]["units"] == "ft"
        assert activity["range"]["value"] == "120"

    def test_target_reaches_the_activity(self, db):
        item = _feat(db, activation=ItemActivation(
            ItemActivation.ACTION, 1,
            target=ItemTarget(ItemTarget.CONE, ItemRange(15, None, "ft"))))
        activity = next(iter(item.entity["system"]["activities"].values()))
        assert activity["target"]["template"]["type"] == "cone"
        assert activity["target"]["template"]["size"] == "15"


class TestWeaponRange(object):
    """B014: WeaponData declares its own numeric range, not the shared field."""

    def test_weapon_range_is_numeric_with_reach_and_long(self, db):
        item = _weapon(db, activation=ItemActivation(
            ItemActivation.ACTION, 1, range=ItemRange(30, 120, "ft")))
        rng = item.entity["system"]["range"]
        assert rng == {"value": 30, "long": 120, "reach": None, "units": "ft"}

    def test_weapon_range_has_no_special_key(self, db):
        item = _weapon(db, activation=ItemActivation(
            ItemActivation.ACTION, 1, range=ItemRange(5, None, "ft")))
        assert "special" not in item.entity["system"]["range"]

    def test_shared_range_is_a_formula_string_but_weapon_range_is_not(self):
        assert dnd5e.rangeData(30, "ft")["value"] == "30"
        assert dnd5e.weaponRange(30, units="ft")["value"] == 30


class TestCantripSave(object):
    """B015: dnd5e sets onSave="none" for cantrips, but only if the key is absent."""

    def _saveSpell(self, db, level):
        attack = ItemAttack(type=ItemAttack.SAVE, ability="")
        attack.save.ability = "dex"
        attack.save.dc = 13
        attack.damages.damages.append(("1d6", "acid"))
        return _spell(db, "Acid Splash-%d" % level, attack=attack, level=level,
                      activation=ItemActivation(ItemActivation.ACTION, 1))

    def test_cantrip_deals_no_damage_on_a_success(self, db):
        activity = next(iter(
            self._saveSpell(db, 0).entity["system"]["activities"].values()))
        assert activity["damage"]["onSave"] == "none"

    def test_levelled_spell_still_deals_half(self, db):
        activity = next(iter(
            self._saveSpell(db, 1).entity["system"]["activities"].values()))
        assert activity["damage"]["onSave"] == "half"


class TestSaveActivityIsNative(object):
    """B018: save.dc has no `value` and save damage has no `critical` in 5.3.3."""

    def test_dc_is_calculation_and_formula_only(self):
        activity = dnd5e.saveActivity("abc1234567890123", "dex", dc=15)
        assert set(activity["save"]["dc"]) == {"calculation", "formula"}

    def test_save_damage_has_no_critical(self):
        activity = dnd5e.saveActivity("abc1234567890123", "dex", dc=15)
        assert set(activity["damage"]) == {"onSave", "parts"}


class TestRechargeMerges(object):
    """B017: a feature can have both a charge count and a recharge."""

    def test_recharge_alone_sets_uses(self, db):
        item = _feat(db, activation=ItemActivation(ItemActivation.ACTION, 1),
                     recharge=ItemFeatRecharge(5, charged=True))
        assert item.entity["system"]["uses"]["recovery"][0]["period"] == "recharge"

    def test_charges_and_recharge_both_survive(self, db):
        item = _feat(db, activation=ItemActivation(
            ItemActivation.ACTION, 1, uses=ItemUses(3, 3, "day")),
            recharge=ItemFeatRecharge(6, charged=True))
        uses = item.entity["system"]["uses"]
        assert uses["max"] == "3", "the charge count was thrown away"
        periods = [r["period"] for r in uses["recovery"]]
        assert "day" in periods and "recharge" in periods

    def test_no_recharge_leaves_the_charge_count_alone(self, db):
        item = _feat(db, activation=ItemActivation(
            ItemActivation.ACTION, 1, uses=ItemUses(3, 3, "day")))
        assert item.entity["system"]["uses"]["max"] == "3"
