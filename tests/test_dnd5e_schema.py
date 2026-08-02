"""Tests for the dnd5e 5.x schema module (ADR-008).

The converter emitted dnd5e 1.5.6 shapes: ``weaponType``, ``damage.parts``, a
boolean property map, and no activities at all. dnd5e 5.x renamed or restructured
every one of those, and — critically — builds a weapon's default attack in
``WeaponData#_preCreate``, which fires on document *creation* and therefore never
runs for a migrated document. A converted world consequently arrives with every
weapon unrollable.

These tests pin the shapes and, more importantly, the *invariants*: chiefly that
moving a baked-in ability modifier out of the damage and into the activity leaves
the printed damage total unchanged.

Test ids match the QA plan (TC-15-xx foundation, TC-16-xx damage, TC-17-xx
properties, TC-18-xx activities, INV-xx damage invariants).
"""

import pytest

import dnd5e


class TestSystemVersion(object):
    """AD-5: the version we claim must describe the schema we emit."""

    def testTargetsFivePointX(self):
        assert dnd5e.SYSTEM_VERSION.startswith("5.")

    def testMinimumIsTheActivitiesGeneration(self):
        # Activities landed in dnd5e 4.0; anything older cannot read our output.
        assert dnd5e.MINIMUM_SYSTEM_VERSION >= "5.0.0"

    def testAbilityOrderIsFixed(self):
        # Tie-breaking depends on this order (AD-4); a set or dict would make
        # the converter's output vary between runs.
        assert dnd5e.ABILITIES == ("str", "dex", "con", "int", "wis", "cha")


class TestItemType(object):
    """TC-15-01..07: ``system.type`` replaces the four separate type fields."""

    def testWeaponTypeShape(self):
        result = dnd5e.itemType("martialM", "longsword")
        assert result == {"value": "martialM", "baseItem": "longsword"}

    def testEmptyBaseItemIsLegal(self):
        # Most converted content is bespoke monster attacks with no SRD match.
        assert dnd5e.itemType("natural")["baseItem"] == ""

    def testKnownWeaponTypesAreTheDnd5eSet(self):
        assert "martialM" in dnd5e.WEAPON_TYPES
        assert "natural" in dnd5e.WEAPON_TYPES
        # v1.5.6 had "ammo"; 5.x does not.
        assert "ammo" not in dnd5e.WEAPON_TYPES


class TestBaseItemResolution(object):
    """TC-15-01/04, AD-7: resolve by table, never guess."""

    @pytest.mark.parametrize("name,expected", [
        ("Longsword", "longsword"),
        ("longsword", "longsword"),
        ("Dagger", "dagger"),
        ("Greatsword", "greatsword"),
        ("Shortbow", "shortbow"),
        ("Quarterstaff", "quarterstaff"),
    ])
    def testPlainNamesResolve(self, name, expected):
        assert dnd5e.weaponBaseItem(name) == expected

    @pytest.mark.parametrize("name,expected", [
        ("Longsword (Melee; Two-Handed)", "longsword"),
        ("Shortsword +1", "shortsword"),
        ("Dagger, Silvered", "dagger"),
        ("Hand Crossbow", "handcrossbow"),
        ("Light Crossbow", "lightcrossbow"),
        ("War Pick", "warpick"),
    ])
    def testQualifiedNamesResolve(self, name, expected):
        # Roll20 names carry qualifiers that a naive slug lookup would miss.
        assert dnd5e.weaponBaseItem(name) == expected

    @pytest.mark.parametrize("name", [
        "Bite", "Claw", "Tentacles", "Corrupting Touch", "Goblin Spiked Thing", "", None,
    ])
    def testUnknownNamesYieldEmptyNotAGuess(self, name):
        # A wrong slug makes dnd5e apply the wrong properties and proficiency —
        # worse than no slug at all.
        assert dnd5e.weaponBaseItem(name) == ""

    def testArmorResolves(self):
        assert dnd5e.armorBaseItem("Chain Mail") == "chainmail"
        assert dnd5e.armorBaseItem("Studded Leather") == "studded"
        assert dnd5e.armorBaseItem("Fancy Robe") == ""


class TestProperties(object):
    """TC-17-01..04: the boolean map becomes an array."""

    def testSelectedKeysOnly(self):
        result = dnd5e.properties({"ver": True, "two": True, "amm": False, "hvy": False})
        assert result == ["two", "ver"]

    def testResultIsAList(self):
        assert isinstance(dnd5e.properties({"ver": True}), list)

    def testEmptyMapYieldsEmptyList(self):
        assert dnd5e.properties({"ver": False, "two": False}) == []
        assert dnd5e.properties({}) == []

    def testUnknownKeysAreDropped(self):
        # An invalid property key fails validation for the whole item.
        assert dnd5e.properties({"banana": True, "ver": True}) == ["ver"]

    def testOrderIsDeterministic(self):
        a = dnd5e.properties({"two": True, "ver": True, "fin": True})
        b = dnd5e.properties({"fin": True, "ver": True, "two": True})
        assert a == b

    def testAcceptsAlreadyAList(self):
        assert dnd5e.properties(["ver", "two"]) == ["two", "ver"]


class TestDamageType(object):
    """TC-16-05/06/07: real Roll20 damage types are dirty."""

    def testCleanTypePassesThrough(self):
        assert dnd5e.normalizeDamageType("slashing") == "slashing"

    def testWhitespaceIsStripped(self):
        # Observed in real exports: "bludgeoning ", "poison ".
        assert dnd5e.normalizeDamageType("bludgeoning ") == "bludgeoning"
        assert dnd5e.normalizeDamageType(" poison") == "poison"

    def testCaseIsNormalized(self):
        assert dnd5e.normalizeDamageType("Piercing") == "piercing"

    def testCompoundTypeTakesFirstRecognised(self):
        # "bludgeoning or slashing" — keep it typed rather than dropping it.
        assert dnd5e.normalizeDamageType("bludgeoning or slashing") == "bludgeoning"

    @pytest.mark.parametrize("value", ["spell", "none", "", None, "wibble"])
    def testUnrecognisedYieldsNone(self, value):
        # None means "emit no type", which is valid. Emitting the raw value
        # would fail schema validation.
        assert dnd5e.normalizeDamageType(value) is None


class TestDamageData(object):
    """TC-16-01..04: ``damage.parts`` becomes a ``DamageData`` object."""

    def testBasicShape(self):
        result = dnd5e.damageData(1, 8, "", ["slashing"])
        assert result["number"] == 1
        assert result["denomination"] == 8
        assert result["types"] == ["slashing"]
        assert result["custom"] == {"enabled": False, "formula": ""}
        assert result["scaling"]["number"] == 1

    def testTypesIsAList(self):
        # DamageData.types is a SetField, which serialises as an array.
        assert isinstance(dnd5e.damageData(1, 6, types=["fire"])["types"], list)

    def testTypesAreNormalizedAndDeduplicated(self):
        result = dnd5e.damageData(1, 6, types=["fire ", "Fire", "wibble"])
        assert result["types"] == ["fire"]

    def testZeroBonusIsEmptyString(self):
        # bonus is a FormulaField; "0" would render as a visible "+0".
        assert dnd5e.damageData(1, 8, 0)["bonus"] == ""
        assert dnd5e.damageData(1, 8, "0")["bonus"] == ""
        assert dnd5e.damageData(1, 8, 2)["bonus"] == "2"

    def testCustomFormulaEnablesCustom(self):
        result = dnd5e.damageData(custom_formula="1d6 + 1d8")
        assert result["custom"] == {"enabled": True, "formula": "1d6 + 1d8"}

    def testNoLegacyPartsKey(self):
        assert "parts" not in dnd5e.damageData(1, 8)


class TestParseDamageFormula(object):
    """TC-16-08/09/10: degenerate formulas are real and must survive."""

    @pytest.mark.parametrize("formula,expected", [
        ("1d8", (1, 8, 0, "")),
        ("2d6", (2, 6, 0, "")),
        ("1d10+2", (1, 10, 2, "")),
        ("1d10 + 2", (1, 10, 2, "")),
        ("2d6 - 1", (2, 6, -1, "")),
    ])
    def testDiceAndBonus(self, formula, expected):
        assert dnd5e.parseDamageFormula(formula) == expected

    @pytest.mark.parametrize("formula,expected", [
        ("1d0", (1, 0, 0, "")),       # nets
        ("1d1", (1, 1, 0, "")),       # gas spore touch
        ("1", (None, None, 1, "")),   # torches
        ("7", (None, None, 7, "")),
    ])
    def testDegenerateFormulasSurvive(self, formula, expected):
        assert dnd5e.parseDamageFormula(formula) == expected

    def testSecondDieBecomesRemainder(self):
        # "1d6 + 3 + 1d8" — the 1d8 must not be silently lost.
        number, denom, bonus, remainder = dnd5e.parseDamageFormula("1d6 + 3 + 1d8")
        assert (number, denom, bonus) == (1, 6, 3)
        assert "1d8" in remainder

    def testSymbolicModifierBecomesRemainder(self):
        number, denom, bonus, remainder = dnd5e.parseDamageFormula(
            "1d8 + @abilities.str.mod")
        assert (number, denom, bonus) == (1, 8, 0)
        assert "@abilities.str.mod" in remainder

    @pytest.mark.parametrize("formula", ["", None, "   "])
    def testEmptyFormula(self, formula):
        assert dnd5e.parseDamageFormula(formula) == (None, None, 0, "")


class TestModifierExtractionInvariant(object):
    """INV-01..17 — the single most important property in this port.

    dnd5e appends ``@mod`` to weapon damage, resolved from the activity's
    ability. Roll20 bakes that modifier into the damage. The extraction must
    leave the *printed total* unchanged:

        printed == result.bonus + (mod applied by dnd5e)

    where dnd5e applies a modifier only for a **weapon** whose base damage is
    **not deterministic** — see ``appendsAbilityModifier``.
    """

    # id, baked bonus, ability mods, ranged, symbolic, expected ability, expected bonus
    FIXTURES = [
        ("INV-01", 2, {"str": 2, "dex": 1}, False, None, "str", 0),
        ("INV-02", 3, {"str": 3, "dex": 4}, False, None, "str", 0),
        ("INV-03", 0, {"str": 3, "dex": 3}, False, "str", "str", 0),
        # B005: no ability matches +5. Subtracting the natural ability's
        # modifier still preserves the total; "flat" cannot suppress @mod.
        ("INV-06", 5, {"str": 3, "dex": 2}, False, None, "str", 2),
        ("INV-07", -1, {"str": -1, "dex": 2}, False, None, "str", 0),
        ("INV-08", 0, {"str": 0, "dex": 2}, False, None, "str", 0),
        ("INV-09", 2, {"str": 2, "dex": 2}, False, None, "str", 0),
        ("INV-12", 0, {"str": 3, "dex": 2}, True, "dex", "dex", 0),
        ("INV-13", 4, {"str": 4, "dex": 1}, True, None, "str", 0),
        ("INV-14", 3, {"str": 1, "dex": 3}, True, None, "dex", 0),
        ("INV-15", 0, {"str": 3, "dex": 2, "con": 4}, False, None, "str", -3),
        # B001: a symbolic modifier alongside a flat addend — "1d8 +
        # @abilities.str.mod + 1". The symbolic term moves into the activity;
        # the "+1" must stay on the damage or the printed total drops by 1.
        ("INV-16", 1, {"str": 3}, False, "str", "str", 1),
        ("INV-17", 2, {"str": 4, "dex": 1}, True, "dex", "dex", 2),
        ("INV-18", 7, {"str": 2, "dex": 1}, False, None, "str", 5),
    ]

    @pytest.mark.parametrize(
        "case_id,bonus,mods,ranged,symbolic,want_ability,want_bonus", FIXTURES)
    def testExtraction(self, case_id, bonus, mods, ranged, symbolic,
                       want_ability, want_bonus):
        result = dnd5e.extractAbilityModifier(bonus, mods, ranged=ranged, symbolic=symbolic)
        assert result.ability == want_ability, case_id
        assert result.bonus == want_bonus, case_id

    @pytest.mark.parametrize(
        "case_id,bonus,mods,ranged,symbolic,want_ability,want_bonus", FIXTURES)
    def testPrintedTotalIsPreserved(self, case_id, bonus, mods, ranged, symbolic,
                                    want_ability, want_bonus):
        """The invariant itself, asserted independently of the expected values.

        B001 hid here: this used to read ``expected = bonus if not symbolic else
        mods[symbolic]``, which discards the flat bonus in the symbolic case and
        so ratified an implementation that dropped it.
        """
        result = dnd5e.extractAbilityModifier(bonus, mods, ranged=ranged, symbolic=symbolic)
        # A weapon with dice damage always gets @mod from the chosen ability.
        applied = mods.get(result.ability, 0)
        printed = bonus + (mods.get(symbolic, 0) if symbolic else 0)
        assert result.bonus + applied == printed, (
            "%s: printed total changed — %s + %s != %s"
            % (case_id, result.bonus, applied, printed))

    @pytest.mark.parametrize(
        "case_id,bonus,mods,ranged,symbolic,want_ability,want_bonus", FIXTURES)
    def testPrintedTotalIsPreservedWithoutAutoModifier(
            self, case_id, bonus, mods, ranged, symbolic, want_ability, want_bonus):
        """B005: spells, feats and flat damage receive no ``@mod`` at all.

        Nothing is appended, so nothing may be subtracted — the damage must come
        out exactly as printed.
        """
        for kwargs in ({"is_weapon": False}, {"has_dice": False}):
            result = dnd5e.extractAbilityModifier(
                bonus, mods, ranged=ranged, symbolic=symbolic, **kwargs)
            printed = bonus + (mods.get(symbolic, 0) if symbolic else 0)
            assert result.bonus == printed, (
                "%s %s: damage changed — %s != %s"
                % (case_id, kwargs, result.bonus, printed))

    def testFixtureTableIsNonVacuous(self):
        # A table-driven test that silently runs zero rows is worse than no test.
        assert len(self.FIXTURES) >= 10
        # Every branch of the extractor must be exercised.
        assert any(f[4] for f in self.FIXTURES), "no symbolic case"
        assert any(f[1] < 0 for f in self.FIXTURES), "no negative modifier case"
        assert any(f[4] and f[1] for f in self.FIXTURES), "no symbolic-plus-flat case (B001)"
        assert any(f[6] not in (0,) for f in self.FIXTURES), "no residual-bonus case (B005)"

    def testUnmatchedBonusSubtractsRatherThanGoingFlat(self):
        """B005 regression.

        ``attack.flat`` makes the *attack roll* a flat bonus; it has no effect on
        damage, so it cannot be used to suppress ``@mod``. The residual must
        absorb the difference instead.
        """
        result = dnd5e.extractAbilityModifier(5, {"str": 3, "dex": 2})
        assert result.flat is False
        assert result.bonus == 2
        assert result.bonus + 3 == 5

    def testFlatDamageIsLeftAlone(self):
        """A torch deals a flat 1 — deterministic, so dnd5e appends no @mod."""
        result = dnd5e.extractAbilityModifier(1, {"str": 3}, has_dice=False)
        assert result.bonus == 1

    def testSpellDamageIsLeftAlone(self):
        # The @mod block in _processDamagePart only runs for item.type "weapon".
        result = dnd5e.extractAbilityModifier(3, {"str": 3}, is_weapon=False)
        assert result.bonus == 3

    def testSymbolicOnANonWeaponMaterialisesTheModifier(self):
        # Nothing will append @mod, so the named modifier must be written out.
        result = dnd5e.extractAbilityModifier(0, {"str": 3}, symbolic="str", is_weapon=False)
        assert result.bonus == 3

    def testAppendsAbilityModifierMatchesTheSystem(self):
        assert dnd5e.appendsAbilityModifier(is_weapon=True, has_dice=True) is True
        assert dnd5e.appendsAbilityModifier(is_weapon=True, has_dice=False) is False
        assert dnd5e.appendsAbilityModifier(is_weapon=False, has_dice=True) is False

    def testSymbolicKeepsFlatAddend(self):
        """B001 regression — "1d8 + @abilities.str.mod + 1"."""
        result = dnd5e.extractAbilityModifier(1, {"str": 3}, symbolic="str")
        assert result.ability == "str"
        assert result.bonus == 1, "the +1 was dropped; printed total fell by 1"

    def testSymbolicIsCaseInsensitive(self):
        # ABILITY_MOD_RE matches case-insensitively, so "STR" reaches us.
        assert dnd5e.extractAbilityModifier(0, {"str": 2}, symbolic="STR").ability == "str"

    def testUnknownSymbolicAbilityRaises(self):
        with pytest.raises(ValueError):
            dnd5e.extractAbilityModifier(0, {"str": 2}, symbolic="banana")

    def testRemainderIsPassedThrough(self):
        result = dnd5e.extractAbilityModifier(3, {"str": 3}, remainder="1d8")
        assert result.remainder == "1d8"

    def testNoAbilitiesAtAllDoesNotCrash(self):
        result = dnd5e.extractAbilityModifier(2, {}, ranged=True)
        assert result.ability == "dex"
        assert result.bonus == 2


class TestActivities(object):
    """TC-18-01..04, AD-3: the converter builds activities itself."""

    def testAttackActivityShape(self):
        activity = dnd5e.attackActivity("abc123", "str")
        assert activity["type"] == "attack"
        assert activity["attack"]["ability"] == "str"
        assert activity["attack"]["type"] == {"value": "melee", "classification": "weapon"}
        assert activity["damage"]["includeBase"] is True

    def testRangedClassification(self):
        activity = dnd5e.attackActivity("abc123", "dex", ranged=True)
        assert activity["attack"]["type"]["value"] == "ranged"

    def testIdMatchesKeyField(self):
        # The activities collection is keyed by id; a mismatch orphans the entry.
        activity = dnd5e.attackActivity("deadbeefdeadbeef", "str")
        assert activity["_id"] == "deadbeefdeadbeef"

    def testAbilityNoneIsRejected(self):
        # TC-18-04 / D3: "none" reads back as null and is documented as making
        # @mod resolve to 0, but writing it fails validation and the activity is
        # then silently not created. Fail loudly here instead.
        with pytest.raises(ValueError):
            dnd5e.attackActivity("abc123", "none")

    @pytest.mark.parametrize("ability", ["STR", "banana", "strength", "Str"])
    def testInvalidAbilityIsRejected(self, ability):
        # B002: "none" was the only rejected value, so "STR" sailed through and
        # produced an activity dnd5e validates away just as silently.
        with pytest.raises(ValueError):
            dnd5e.attackActivity("abc123", ability)

    def testEmptyAbilityIsAllowed(self):
        # An empty ability is legal — it means "no modifier", unlike "none".
        assert dnd5e.attackActivity("abc123", "")["attack"]["ability"] == ""

    def testFlatSuppressesTheModifier(self):
        activity = dnd5e.attackActivity("abc123", "str", flat=True)
        assert activity["attack"]["flat"] is True

    def testActivityIdIsSixteenChars(self):
        assert len(dnd5e.activityId("anything")) == 16

    def testActivityIdIsDeterministic(self):
        # Converting the same export twice must produce identical output.
        assert dnd5e.activityId("actor:weapon") == dnd5e.activityId("actor:weapon")
        assert dnd5e.activityId("a") != dnd5e.activityId("b")

    def testActivityIdIsAlphanumeric(self):
        assert dnd5e.activityId("x").isalnum()

    def testSaveActivityShape(self):
        activity = dnd5e.saveActivity("abc123", "dex", dc=15)
        assert activity["type"] == "save"
        assert activity["save"]["ability"] == ["dex"]
        assert activity["save"]["dc"]["formula"] == "15"
        assert "value" not in activity["save"]["dc"]

    def testDamageActivityShape(self):
        activity = dnd5e.damageActivity("abc123", [dnd5e.damageData(2, 6, types=["fire"])])
        assert activity["type"] == "damage"
        assert len(activity["damage"]["parts"]) == 1

    def testUtilityActivityHasNoRoll(self):
        activity = dnd5e.utilityActivity("abc123")
        assert activity["type"] == "utility"
        assert "attack" not in activity
        assert "damage" not in activity

    def testNoLegacyActionFields(self):
        activity = dnd5e.attackActivity("abc123", "str")
        for legacy in ("actionType", "attackBonus", "chatFlavor", "formula"):
            assert legacy not in activity


class TestStats(object):
    """AD-5: ``_stats`` was emitted nowhere; dnd5e reads it to decide migration."""

    def testShape(self):
        result = dnd5e.stats("13")
        assert result["systemId"] == "dnd5e"
        assert result["systemVersion"] == dnd5e.SYSTEM_VERSION
        assert result["coreVersion"] == "13"

    def testSystemVersionTellsTheTruth(self):
        # Claiming an older version runs a migration over documents that have no
        # legacy fields left to convert, which empties system.damage.base.
        assert dnd5e.stats("13")["systemVersion"].startswith("5.")
