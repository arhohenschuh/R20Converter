"""B054: a magic AC bonus must not overwrite the base armor value.

Roll20 lists both under the same `AC` name in `itemmodifiers`, e.g.
`"Item Type: Medium Armor, AC: 15, AC +2"`. The parser used a flat dict, so the
bonus overwrote the base and `int("+2")` became the armour value -- Sylvaris'
Half Plate +2 shipped as AC 4 instead of 21.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from entities.actors import parseItemModifiers
from entities.items import ItemEquipment


class TestMagicArmorKeepsBaseValue(object):
    # Verbatim `itemmodifiers` strings from the affected exports.
    @pytest.mark.parametrize("mods,base,bonus", [
        ("Item Type: Medium Armor, AC: 15, AC +2, Stealth:Disadvantage", "15", "+2"),
        ("Item Type: Medium Armor, AC: 14, AC +1", "14", "+1"),
        ("Item Type: Medium Armor, AC: 13, AC +1", "13", "+1"),
    ])
    def test_base_survives_the_bonus(self, mods, base, bonus):
        modifiers = parseItemModifiers(mods)
        assert modifiers["AC"] == base, "the magic bonus overwrote the base armor value"
        assert modifiers["AC bonus"] == bonus

    def test_bonus_listed_first_still_yields_the_base(self):
        modifiers = parseItemModifiers("Item Type: Heavy Armor, AC +3, AC: 18")
        assert modifiers["AC"] == "18"
        assert modifiers["AC bonus"] == "+3"

    def test_other_modifiers_are_untouched(self):
        modifiers = parseItemModifiers(
            "Item Type: Medium Armor, AC: 15, AC +2, Stealth:Disadvantage")
        assert modifiers["Item Type"] == "Medium Armor"
        assert modifiers["Stealth"] == "Disadvantage"

    def test_a_lone_bonus_is_still_the_ac(self):
        # A Ring of Protection has no base armor; the sole `AC +1` stays under "AC".
        modifiers = parseItemModifiers("Item Type: Ring, AC +1")
        assert modifiers["AC"] == "+1"
        assert "AC bonus" not in modifiers

    def test_mundane_armor_gets_no_bonus_key(self):
        modifiers = parseItemModifiers("Item Type: Heavy Armor, AC: 16, Stealth:Disadvantage")
        assert modifiers["AC"] == "16"
        assert "AC bonus" not in modifiers

    def test_malformed_input_does_not_crash(self):
        assert parseItemModifiers("") == {}
        assert parseItemModifiers("Sunder") == {"Sunder": "Sunder"}


class TestEquipmentEmitsMagicalBonus(object):
    def test_bonus_is_emitted(self):
        armor = ItemEquipment(ItemEquipment.MEDIUM_ARMOR, ac=15, magical_bonus=2)
        assert armor.getDict()["armor"] == {"value": 15, "dex": 2, "magicalBonus": 2}

    def test_mundane_armor_reports_no_bonus(self):
        armor = ItemEquipment(ItemEquipment.HEAVY_ARMOR, ac=16)
        assert armor.getDict()["armor"]["magicalBonus"] is None
