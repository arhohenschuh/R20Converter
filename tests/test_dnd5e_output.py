"""R2 — the dnd5e 5.x output switch (ADR-008).

These are the tests that decide whether the switch actually happened. The
convention from ``test_document_schema.py`` applies throughout: assert that the
legacy field is **absent**, not merely that its replacement is present. A rename
that leaves both in place still produces a document dnd5e reads wrongly.

The invariant that matters most is that a weapon's *printed damage total* is
unchanged after the baked-in ability modifier is moved into the activity. dnd5e
appends ``@mod`` to a weapon's damage from the activity's ability, so leaving the
modifier in the damage double-counts it.
"""

import pytest

import dnd5e
from entities.items import Item, ItemAttack, ItemDamage, ItemWeapon, \
    ItemWeaponProperties, ItemEquipment, ItemConsumable, ItemTool, ItemSave

from conftest import FakeDatabase


LEGACY_ITEM_FIELDS = ("weaponType", "armorType", "consumableType", "toolType",
                      "baseItem", "actionType", "attackBonus", "formula",
                      "chatFlavor", "critical", "save")


@pytest.fixture
def db(tmp_path):
    return FakeDatabase(str(tmp_path), {})


def makeWeapon(db, name="Longsword", formula="1d8 + 3", damage_type="slashing",
               mods=None, action=ItemAttack.MELEE_WEAPON, weapon_type="martialM",
               versatile="", properties=(), bonus=0):
    damage = ItemDamage(versatile=versatile)
    if formula is not None:
        damage.addDamage(formula, damage_type)
    attack = ItemAttack(type=action, ability="", damages=damage, bonus=bonus)
    props = ItemWeaponProperties()
    for prop in properties:
        props.addProperty(prop)
    weapon = ItemWeapon(_type=weapon_type, properties=props)
    return Item.createItemWeapon(db, "w1", name, "", None, attack, None, weapon,
                                 ability_mods=mods or {"str": 3, "dex": 1})


class TestLegacyFieldsAreGone(object):
    """TC-15/16/17/18: the switch removes, it does not accompany."""

    def testWeapon(self, db):
        system = makeWeapon(db).entity["system"]
        for field in LEGACY_ITEM_FIELDS:
            assert field not in system, "legacy %r still emitted" % field

    def testNoLegacyDamageParts(self, db):
        system = makeWeapon(db).entity["system"]
        assert "parts" not in system["damage"]

    def testPropertiesIsAnArray(self, db):
        system = makeWeapon(db, properties=("ver", "two")).entity["system"]
        assert isinstance(system["properties"], list)
        assert set(system["properties"]) == {"ver", "two"}

    def testEquipment(self, db):
        item = Item.createItemEquipment(db, "e1", "Chain Mail", "", None, None,
                                        None, ItemEquipment(_type="heavy", ac=16))
        system = item.entity["system"]
        assert "baseItem" not in system
        assert "type" not in system["armor"], "armor.type moved to system.type"
        assert system["type"] == {"value": "heavy", "baseItem": "chainmail"}

    def testConsumable(self, db):
        item = Item.createItemConsumable(db, "c1", "Potion of Healing", "", None,
                                         None, None, ItemConsumable(_type="potion"))
        system = item.entity["system"]
        assert "consumableType" not in system
        assert system["type"]["value"] == "potion"

    def testTool(self, db):
        item = Item.createItemTool(db, "t1", "Thieves' Tools", "", None, ItemTool())
        system = item.entity["system"]
        assert "toolType" not in system
        assert "baseItem" not in system
        assert "type" in system


class TestItemType(object):
    """TC-15-01..07."""

    def testWeaponTypeAndBaseItem(self, db):
        system = makeWeapon(db, name="Longsword").entity["system"]
        assert system["type"] == {"value": "martialM", "baseItem": "longsword"}

    def testQualifiedNameStillResolves(self, db):
        system = makeWeapon(db, name="Longsword (Melee; Two-Handed)").entity["system"]
        assert system["type"]["baseItem"] == "longsword"

    def testMonsterAttackHasNoBaseItem(self, db):
        # Bespoke attacks have no SRD equivalent; empty is correct, and better
        # than a wrong slug that would apply the wrong mastery and properties.
        system = makeWeapon(db, name="Bite", weapon_type="natural").entity["system"]
        assert system["type"] == {"value": "natural", "baseItem": ""}


class TestActivities(object):
    """TC-18: every rollable item gets an activity, built at creation time."""

    def testWeaponHasAnAttackActivity(self, db):
        system = makeWeapon(db).entity["system"]
        activities = system["activities"]
        assert len(activities) == 1
        activity = list(activities.values())[0]
        assert activity["type"] == "attack"
        assert activity["attack"]["type"] == {"value": "melee", "classification": "weapon"}

    def testActivityKeyMatchesItsId(self, db):
        activities = makeWeapon(db).entity["system"]["activities"]
        for key, activity in activities.items():
            assert key == activity["_id"], "a mismatch orphans the activity"
            assert len(key) == 16

    def testRangedWeaponIsClassifiedRanged(self, db):
        system = makeWeapon(db, name="Longbow", action=ItemAttack.RANGED_WEAPON,
                            weapon_type="martialR", mods={"str": 1, "dex": 3},
                            formula="1d8 + 3").entity["system"]
        activity = list(system["activities"].values())[0]
        assert activity["attack"]["type"]["value"] == "ranged"

    def testAbilityIsNeverNone(self, db):
        # D3: "none" reads back as null but fails validation on write, and the
        # activity is then silently not created.
        system = makeWeapon(db).entity["system"]
        for activity in system["activities"].values():
            assert activity.get("attack", {}).get("ability") != "none"

    def testIdsAreDeterministic(self, db):
        first = sorted(makeWeapon(db).entity["system"]["activities"])
        second = sorted(makeWeapon(db).entity["system"]["activities"])
        assert first == second, "repeat conversions must be byte-identical"

    def testUnrollableItemGetsNoActivity(self, db):
        # An empty activity puts an unusable button on the sheet.
        item = Item.createItemTool(db, "t1", "Thieves' Tools", "", None, ItemTool())
        assert not item.entity["system"].get("activities")

    def testSaveActionBuildsASaveActivity(self, db):
        damage = ItemDamage()
        damage.addDamage("8d6", "fire")
        save = ItemSave(ability="dex", dc=15)
        attack = ItemAttack(type=ItemAttack.SAVE, damages=damage, save=save)
        item = Item.createItemSpell(db, "s1", "Fireball", "", None, attack,
                                    3, "evo", None, None, None,
                                    ability_mods={"int": 4})
        activity = list(item.entity["system"]["activities"].values())[0]
        assert activity["type"] == "save"
        assert activity["save"]["ability"] == ["dex"]
        assert activity["save"]["dc"]["formula"] == "15"
        assert "value" not in activity["save"]["dc"], \
            "SaveActivityData#save.dc is {calculation, formula} in 5.3.3"


class TestDamageInvariant(object):
    """The property the whole port exists to protect.

    dnd5e appends ``@mod`` to a weapon's damage from the activity's ability, so
    the emitted damage plus that modifier must equal what Roll20 printed.
    """

    def totalOf(self, system, mods):
        base = system["damage"]["base"]
        activity = list(system["activities"].values())[0]
        ability = activity.get("attack", {}).get("ability") or ""
        applied = mods.get(ability, 0) if base["number"] else 0
        return int(base["bonus"] or 0) + applied

    @pytest.mark.parametrize("formula,mods,printed", [
        ("1d8 + 3", {"str": 3, "dex": 1}, 3),      # exact match -> residual 0
        ("1d10 + 2", {"str": 2, "dex": 1}, 2),
        ("2d6 + 5", {"str": 3, "dex": 2}, 5),      # no match  -> residual absorbs
        ("1d6 - 1", {"str": -1, "dex": 2}, -1),    # negative modifier
        ("1d8", {"str": 3, "dex": 1}, 0),          # no bonus at all
        ("1d4 + 7", {"str": 2, "dex": 1}, 7),
    ])
    def testPrintedTotalIsPreserved(self, db, formula, mods, printed):
        system = makeWeapon(db, formula=formula, mods=mods).entity["system"]
        assert self.totalOf(system, mods) == printed

    def testBakedModifierMovesOutOfTheDamage(self, db):
        # The visible symptom of getting this wrong is 1d8+3+@mod = 1d8+6.
        system = makeWeapon(db, formula="1d8 + 3", mods={"str": 3}).entity["system"]
        assert system["damage"]["base"]["bonus"] == ""

    def testDamageTypeSurvives(self, db):
        system = makeWeapon(db, damage_type="slashing").entity["system"]
        assert system["damage"]["base"]["types"] == ["slashing"]

    def testDirtyDamageTypeIsNormalized(self, db):
        # D6: real exports carry "bludgeoning " and "bludgeoning or slashing".
        system = makeWeapon(db, damage_type="bludgeoning ").entity["system"]
        assert system["damage"]["base"]["types"] == ["bludgeoning"]

    @pytest.mark.parametrize("formula", ["1d0", "1", "1d1"])
    def testDegenerateDamageSurvives(self, db, formula):
        # D5: nets roll 1d0, torches deal a flat 1, a gas spore's touch is 1d1.
        system = makeWeapon(db, formula=formula).entity["system"]
        base = system["damage"]["base"]
        assert base["number"] is not None or base["bonus"] != "", \
            "damage vanished for %r" % formula
        assert system["activities"], "no activity for %r" % formula

    def testSecondDamageDieIsNotLost(self, db):
        # "1d6 + 3 + 1d8" has no home in the dice fields; it must become a
        # custom formula rather than silently dropping the 1d8.
        system = makeWeapon(db, formula="1d6 + 3 + 1d8",
                            mods={"str": 3}).entity["system"]
        base = system["damage"]["base"]
        blob = base["custom"]["formula"] if base["custom"]["enabled"] else ""
        assert "1d8" in blob, "the second die was dropped"

    def testSymbolicModifierIsNotDoubleCounted(self, db):
        # D2: pregenerated PCs write "@abilities.str.mod" instead of a number.
        system = makeWeapon(db, formula="1d8 + @abilities.str.mod",
                            mods={"str": 3}).entity["system"]
        base = system["damage"]["base"]
        blob = (base["custom"]["formula"] if base["custom"]["enabled"] else "") \
            + str(base["bonus"])
        assert "@abilities" not in blob, "@mod would be applied twice"
        assert base["bonus"] == ""

    def testVersatileIsAnObject(self, db):
        system = makeWeapon(db, versatile="1d10").entity["system"]
        versatile = system["damage"]["versatile"]
        assert isinstance(versatile, dict)
        assert versatile["number"] == 1 and versatile["denomination"] == 10


class TestMultipleDamageParts(object):
    """A second typed part belongs on the activity, not lost."""

    def testSecondPartBecomesAnActivityPart(self, db):
        damage = ItemDamage()
        damage.addDamage("2d6 + 5", "slashing")
        damage.addDamage("1d6", "fire")
        attack = ItemAttack(type=ItemAttack.MELEE_WEAPON, damages=damage)
        item = Item.createItemWeapon(db, "w1", "Flame Tongue", "", None, attack,
                                     None, ItemWeapon(_type="martialM"),
                                     ability_mods={"str": 5})
        system = item.entity["system"]
        assert system["damage"]["base"]["types"] == ["slashing"]
        activity = list(system["activities"].values())[0]
        assert len(activity["damage"]["parts"]) == 1
        assert activity["damage"]["parts"][0]["types"] == ["fire"]

    def testIncludeBaseIsSetForWeapons(self, db):
        system = makeWeapon(db).entity["system"]
        activity = list(system["activities"].values())[0]
        assert activity["damage"]["includeBase"] is True


class TestSpellsAndFeats(object):
    """Spells and feats are not weapons: dnd5e appends no @mod to their damage."""

    def testSpellDamageIsNotReduced(self, db):
        damage = ItemDamage()
        damage.addDamage("8d6", "fire")
        attack = ItemAttack(type=ItemAttack.RANGED_SPELL, damages=damage)
        item = Item.createItemSpell(db, "s1", "Fireball", "", None, attack,
                                    3, "evo", None, None, None,
                                    ability_mods={"int": 4})
        system = item.entity["system"]
        # A spell carries no system.damage.base; the damage lives on the activity.
        assert "parts" not in system.get("damage", {})
        activity = list(system["activities"].values())[0]
        assert activity["damage"]["parts"][0]["number"] == 8

    def testSpellActivityIsClassifiedSpell(self, db):
        damage = ItemDamage()
        damage.addDamage("1d10", "fire")
        attack = ItemAttack(type=ItemAttack.RANGED_SPELL, damages=damage)
        item = Item.createItemSpell(db, "s2", "Fire Bolt", "", None, attack,
                                    0, "evo", None, None, None,
                                    ability_mods={"int": 4})
        activity = list(item.entity["system"]["activities"].values())[0]
        assert activity["attack"]["type"]["classification"] == "spell"


class TestStats(object):
    """AD-5: dnd5e reads ``_stats.systemVersion`` to decide whether to migrate."""

    def testItemsCarryStats(self, db):
        stats = makeWeapon(db).entity["_stats"]
        assert stats["systemId"] == "dnd5e"
        assert stats["systemVersion"].startswith("5.")

    def testSystemVersionMatchesTheSchemaWeEmit(self):
        import foundry
        assert foundry.DEFAULT_SYSTEM_VERSION == dnd5e.SYSTEM_VERSION
