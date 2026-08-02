"""R3 — origin documents and actor fields against dnd5e 5.3.3.

R2 fixed the item shapes that carry damage. These are the shapes around them:
the class document, and the actor's own ability and skill blocks. The same rule
applies — assert the legacy key is **absent**, because Foundry drops unknown keys
without complaining and a dropped key looks exactly like a correct one until
someone tries to use it at the table.
"""

import pytest

import dnd5e
from entities.items import CLASS_PRIMARY_ABILITY, Item, ItemClass, ItemSubclass

from conftest import FakeDatabase


@pytest.fixture
def db(tmp_path):
    return FakeDatabase(str(tmp_path), {})


class TestClassDocument(object):
    """B019: 5.x replaced `hitDice`/`hitDiceUsed` with the `hd` block."""

    def test_hit_dice_live_in_hd(self):
        data = ItemClass("Barbarian", 3).getDict()
        assert data["hd"]["denomination"] == "d12"
        assert data["hd"]["spent"] == 0
        assert "additional" in data["hd"]

    def test_legacy_hit_dice_keys_are_gone(self):
        data = ItemClass("Wizard", 1).getDict()
        assert "hitDice" not in data
        assert "hitDiceUsed" not in data

    @pytest.mark.parametrize("name,denomination", [
        ("Barbarian", "d12"), ("Fighter", "d10"), ("Paladin", "d10"),
        ("Ranger", "d10"), ("Bard", "d8"), ("Cleric", "d8"), ("Druid", "d8"),
        ("Monk", "d8"), ("Rogue", "d8"), ("Warlock", "d8"),
        ("Sorcerer", "d6"), ("Wizard", "d6"),
    ])
    def test_hit_die_per_class(self, name, denomination):
        """Values from the PHB, not from the implementation's own table."""
        assert ItemClass(name, 1).getDict()["hd"]["denomination"] == denomination

    def test_denomination_always_matches_the_validator(self):
        """ClassData validates `hd.denomination` against /d\\d+/."""
        import re
        for name in list(CLASS_PRIMARY_ABILITY) + ["Unknown Homebrew"]:
            value = ItemClass(name, 1).getDict()["hd"]["denomination"]
            assert re.match(r"^d\d+$", value), "%s -> %r" % (name, value)

    def test_saves_and_skills_are_not_emitted(self):
        """Neither is in ClassData; both were dropped on load."""
        data = ItemClass("Fighter", 1).getDict()
        assert "saves" not in data
        assert "skills" not in data

    def test_primary_ability_is_not_the_spellcasting_ability(self):
        """A Paladin casts on CHA but its primary abilities are STR and CHA."""
        assert ItemClass("Paladin", 1).getDict()["primaryAbility"]["value"] == \
            ["str", "cha"]

    def test_martial_class_has_a_primary_ability_and_no_spellcasting(self):
        data = ItemClass("Fighter", 1).getDict()
        assert data["primaryAbility"]["value"] == ["str"]
        assert data["spellcasting"]["progression"] == "none"

    def test_spellcasting_carries_the_preparation_formula_field(self):
        data = ItemClass("Wizard", 1).getDict()
        assert data["spellcasting"]["progression"] == "full"
        assert data["spellcasting"]["ability"] == "int"
        assert "preparation" in data["spellcasting"]

    def test_every_primary_ability_is_a_real_ability_key(self):
        for abilities in CLASS_PRIMARY_ABILITY.values():
            for ability in abilities:
                assert ability in dnd5e.ABILITIES

    def test_unknown_class_claims_nothing(self):
        """Guessing a primary ability is worse than leaving it unset."""
        assert ItemClass("Bloodhunter", 1).getDict()["primaryAbility"]["value"] == []


class TestSubclassDocument(object):
    def test_links_to_its_class_by_identifier(self):
        data = ItemSubclass("Path of the Berserker", "Barbarian").getDict()
        assert data["classIdentifier"] == "barbarian"
        assert data["identifier"] == "path-of-the-berserker"


class TestSourceField(object):
    """B021: 5.x `source` is a SourceField object, not a string."""

    def test_source_is_an_object(self):
        source = dnd5e.sourceData(custom="Roll 20")
        assert isinstance(source, dict)
        assert source["custom"] == "Roll 20"

    def test_source_carries_every_schema_key(self):
        assert set(dnd5e.sourceData()) == {
            "book", "page", "custom", "license", "revision", "rules"}

    def test_page_is_a_string_even_when_given_a_number(self):
        assert dnd5e.sourceData(page=42)["page"] == "42"

    def test_item_source_is_not_a_bare_string(self, db):
        from entities.items import ItemAttack, ItemWeapon
        attack = ItemAttack(type=ItemAttack.MELEE_WEAPON, ability="str")
        attack.damages.damages.append(("1d8", "slashing"))
        item = Item.createItemWeapon(db, "w1", "Longsword", "", None, attack,
                                     None, ItemWeapon(_type="martialM"),
                                     source="Roll 20", ability_mods={"str": 3})
        source = item.entity["system"]["source"]
        assert isinstance(source, dict), "SourceField is a SchemaField in 5.x"
        assert source["custom"] == "Roll 20"
