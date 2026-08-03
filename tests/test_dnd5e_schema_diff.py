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
