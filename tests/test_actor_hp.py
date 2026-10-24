import pytest

from entities.actors import Actor


class StubActor(object):
    createAttributeHP = Actor.createAttributeHP

    def __init__(self, formula):
        self.formula = formula
        self.warnings = []

    def getName(self):
        return "Generic HP Fixture"

    def logWarning(self, message):
        self.warnings.append(message)

    def isNPC(self):
        return True

    def getAttribute(self, name, default=""):
        if name == "hp":
            return ("20", "20", "source-id")
        if name == "npc_hpformula":
            return (self.formula, None, None)
        return (default, None, None)


def test_valid_hp_formula_is_preserved():
    assert StubActor("4d8 + 12").createAttributeHP()["formula"] == "4d8 + 12"


def test_dynamic_hp_formula_is_preserved():
    formula = "3d8 + (2*@item.level)d8"
    assert StubActor(formula).createAttributeHP()["formula"] == formula


def test_prose_hp_formula_is_cleared():
    formula = "2 + your Intelligence modifier + five times your artificer level"
    assert StubActor(formula).createAttributeHP()["formula"] == ""


@pytest.mark.parametrize("formula", ["22d8 + 22)", "(4d8 + 12", "4d8 +", "4d8 + * 2", "2 3", "()"])
def test_invalid_hp_formula_is_omitted_without_guessing(formula):
    actor = StubActor(formula)
    result = actor.createAttributeHP()
    assert result["formula"] == ""
    assert result["max"] == result["value"] == 20
    warning, = actor.warnings
    assert "npc_hpformula" in warning and "Generic HP Fixture" in warning and formula in warning


@pytest.mark.parametrize("formula", ["22d8 + 22", "max(1, 2d8 + @attributes.prof)", "floor((@level + 1)/2)d8 + 4"])
def test_supported_hp_formula_is_preserved_without_warning(formula):
    actor = StubActor(formula)
    assert actor.createAttributeHP()["formula"] == formula
    assert actor.warnings == []