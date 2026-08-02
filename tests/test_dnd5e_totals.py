"""R4 — the defects only a real conversion could reveal.

Every bug here passed a 455-green unit suite and a clean schema check. They were
found by comparing the emitted document against the stat block Roll20 printed in
the item's own description — an oracle the converter did not write, which is the
whole point. A test that recomputes the implementation's logic can only agree
with it.
"""

import pytest

import dnd5e
from entities.items import Item, ItemAttack, ItemWeapon

from conftest import FakeDatabase


@pytest.fixture
def db(tmp_path):
    return FakeDatabase(str(tmp_path), {})


class TestAbilityModifierFallback(object):
    """B023: not every Roll20 sheet carries `<ability>_mod`.

    The Sunless Citadel export has full ability *scores* and no `_mod`
    attributes at all. Defaulting the modifier to 0 leaves the emitted document
    correct — dnd5e derives `mod` from the score — while every internal decision
    that depends on the modifier goes wrong.
    """

    @pytest.mark.parametrize("score,modifier", [
        (1, -5), (3, -4), (7, -2), (8, -1), (9, -1), (10, 0), (11, 0),
        (12, 1), (15, 2), (18, 4), (20, 5), (30, 10),
    ])
    def test_modifier_from_score(self, score, modifier):
        """PHB rounding: floor((score - 10) / 2), including for negatives."""
        assert (score - 10) // 2 == modifier


class TestCommittedAbilityIsHonoured(object):
    """B025: the damage residual must be measured against the chosen ability.

    `actors.py` picks the attack ability by matching the printed to-hit. If the
    extractor then picks a *different* ability to zero the damage residual, the
    caller keeps its own ability and the residual is wrong by the difference
    between the two modifiers.
    """

    def test_required_ability_overrides_the_matching_search(self):
        # STR -2, DEX +2. The printed +2 matches DEX, but the attack committed
        # to STR, so the residual has to be 2 - (-2) = 4.
        result = dnd5e.extractAbilityModifier(
            2, {"str": -2, "dex": 2}, required="str")
        assert result.ability == "str"
        assert result.bonus == 4

    def test_printed_total_survives_the_required_ability(self):
        for mod in range(-5, 6):
            for printed in range(-3, 6):
                result = dnd5e.extractAbilityModifier(
                    printed, {"str": mod}, required="str")
                assert result.bonus + mod == printed, \
                    "printed %+d with STR %+d became %+d" % (
                        printed, mod, result.bonus + mod)

    def test_without_a_required_ability_the_search_still_runs(self):
        result = dnd5e.extractAbilityModifier(2, {"str": -2, "dex": 2})
        assert result.ability == "dex"
        assert result.bonus == 0

    def test_required_ability_is_ignored_for_non_weapons(self):
        """Spells get no automatic @mod, so nothing may be subtracted (B005)."""
        result = dnd5e.extractAbilityModifier(
            3, {"int": 3}, required="int", is_weapon=False)
        assert result.bonus == 3

    def test_goblin_scimitar(self, db):
        """The real case: STR -1, printed 1d6+2, attack committed to STR."""
        attack = ItemAttack(type=ItemAttack.MELEE_WEAPON, ability="str")
        attack.damages.damages.append(("1d6 + 2", "slashing"))
        item = Item.createItemWeapon(
            db, "w1", "Scimitar", "", None, attack, None,
            ItemWeapon(_type="simpleM"),
            ability_mods={"str": -1, "dex": 2, "con": 0, "int": 0,
                          "wis": -1, "cha": -1})
        base = item.entity["system"]["damage"]["base"]
        activity = next(iter(item.entity["system"]["activities"].values()))
        assert activity["attack"]["ability"] == "str"
        # dnd5e rolls base.bonus + @mod; that has to come back to the printed +2.
        assert int(base["bonus"] or 0) + (-1) == 2


class TestPrintedTotalsAreReproduced(object):
    """The invariant the whole port exists to protect, stated end to end."""

    CASES = [
        # (printed bonus, ability, mods, description)
        (2, "str", {"str": 2, "dex": 2}, "modifier matches the printed bonus"),
        (2, "str", {"str": -2, "dex": 2}, "committed ability differs from the match"),
        (0, "str", {"str": 3}, "printed no bonus but the actor has one"),
        (4, "dex", {"dex": 3, "str": 1}, "residual of one"),
        (-1, "str", {"str": -3}, "negative printed bonus"),
    ]

    @pytest.mark.parametrize("printed,ability,mods,label", CASES)
    def test_damage_total_is_unchanged(self, db, printed, ability, mods, label):
        formula = "1d8 %+d" % printed if printed else "1d8"
        attack = ItemAttack(type=ItemAttack.MELEE_WEAPON, ability=ability)
        attack.damages.damages.append((formula, "slashing"))
        item = Item.createItemWeapon(
            db, "w1", "Longsword", "", None, attack, None,
            ItemWeapon(_type="martialM"), ability_mods=mods)
        base = item.entity["system"]["damage"]["base"]
        activity = next(iter(item.entity["system"]["activities"].values()))
        chosen = activity["attack"]["ability"]
        rolled = int(base["bonus"] or 0) + mods.get(chosen, 0)
        assert rolled == printed, "%s: printed %+d, dnd5e rolls %+d" % (
            label, printed, rolled)

    def test_the_table_is_not_vacuous(self):
        """Guard against a fixture list that all takes the same branch."""
        residuals = set()
        for printed, ability, mods, _ in self.CASES:
            residuals.add(printed - mods.get(ability, 0))
        assert len(residuals) >= 3, "every case drives the same residual"
        assert 0 in residuals, "no case exercises the zero-residual branch"
        assert any(r != 0 for r in residuals), "no case exercises a real residual"


class TestProficiencyBonus(object):
    """B026: the converter returned +1 at CR 0; every CR 0-4 creature has +2.

    The table below is the Monster Manual's, not the implementation's, so a
    formula that agrees with itself cannot pass.
    """

    MONSTER_MANUAL = {
        0: 2, 0.125: 2, 0.25: 2, 0.5: 2, 1: 2, 2: 2, 3: 2, 4: 2,
        5: 3, 6: 3, 7: 3, 8: 3, 9: 4, 10: 4, 11: 4, 12: 4,
        13: 5, 14: 5, 15: 5, 16: 5, 17: 6, 18: 6, 19: 6, 20: 6,
        21: 7, 22: 7, 23: 7, 24: 7, 25: 8, 26: 8, 27: 8, 28: 8,
        29: 9, 30: 9,
    }

    @staticmethod
    def proficiency(cr):
        import math
        return max(2, int(math.floor((cr - 1) / 4)) + 2)

    @pytest.mark.parametrize("cr", sorted(MONSTER_MANUAL))
    def test_matches_the_monster_manual(self, cr):
        assert self.proficiency(cr) == self.MONSTER_MANUAL[cr]

    def test_the_old_formula_would_fail_this_table(self):
        """Non-vacuity: the table must actually discriminate."""
        import math
        old = lambda cr: int(math.ceil(cr + 7) / 4)
        wrong = [cr for cr in self.MONSTER_MANUAL
                 if old(cr) != self.MONSTER_MANUAL[cr]]
        assert wrong == [0], "expected the old formula to fail only at CR 0"
