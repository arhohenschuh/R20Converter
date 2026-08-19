from entities.actors import Actor


class StubActor(object):
    createAttributeHP = Actor.createAttributeHP

    def __init__(self, formula):
        self.formula = formula

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