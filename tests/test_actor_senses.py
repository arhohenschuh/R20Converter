"""Regression tests for actor senses (B044).

dnd5e 5.3 moved the flat sense keys into a ``ranges`` mapping
(``module/data/shared/senses-field.mjs``); the flat shape only survives via a
shim removed in 6.1. Player characters were also skipped entirely, so every PC
converted with darkvision 0 and vision modules -- which read the actor's senses,
not the token's sight range -- granted them nothing.
"""

from entities.actors import Actor, Token


class _StubActor(object):
    """Exercises the senses builder without constructing a whole campaign."""

    createAttributeSenses = Actor.createAttributeSenses
    getCharacterDarkvision = Actor.getCharacterDarkvision

    def __init__(self, npc=False, npc_senses="", token=None):
        self._npc = npc
        self._npc_senses = npc_senses
        self.token = token

    def isNPC(self):
        return self._npc

    def getAttribute(self, name, default=""):
        if name == "npc_senses":
            return (self._npc_senses, None, None)
        return (default, None, None)


def _pc_token(dim=0, bright=0, has_vision=True):
    t = Token("id", "Somebody", None)
    t.has_vision = has_vision
    t.dim_sight = dim
    t.bright_sight = bright
    return t


class TestSensesSchema(object):
    def test_senses_use_the_ranges_mapping(self):
        senses = _StubActor().createAttributeSenses()
        assert "ranges" in senses
        assert set(senses["ranges"]) == {"darkvision", "blindsight", "tremorsense", "truesight"}

    def test_no_flat_sense_keys_remain(self):
        senses = _StubActor().createAttributeSenses()
        for key in ("darkvision", "blindsight", "tremorsense", "truesight"):
            assert key not in senses

    def test_units_and_special_stay_at_the_top_level(self):
        senses = _StubActor().createAttributeSenses()
        assert senses["units"] == "ft"
        assert senses["special"] == ""


class TestNPCSenses(object):
    def test_darkvision_is_parsed_into_ranges(self):
        a = _StubActor(npc=True, npc_senses="darkvision 120 ft., passive Perception 16")
        assert a.createAttributeSenses()["ranges"]["darkvision"] == 120

    def test_multiple_senses_are_parsed(self):
        a = _StubActor(npc=True, npc_senses="blindsight 30 ft., truesight 120 ft.")
        ranges = a.createAttributeSenses()["ranges"]
        assert ranges["blindsight"] == 30
        assert ranges["truesight"] == 120

    def test_passive_perception_is_not_a_special_sense(self):
        a = _StubActor(npc=True, npc_senses="darkvision 60 ft., passive Perception 12")
        assert a.createAttributeSenses()["special"] == ""

    def test_unrecognised_sense_is_kept_as_special(self):
        a = _StubActor(npc=True, npc_senses="darkvision 60 ft., keen smell")
        assert "keen smell" in a.createAttributeSenses()["special"]

    def test_passive_perception_is_matched_case_insensitively(self):
        # Roll20 prints "passive Perception"; the check compared against lowercase.
        a = _StubActor(npc=True, npc_senses="passive Perception 14")
        assert a.createAttributeSenses()["special"] == ""

    def test_consecutive_recognised_senses_are_all_removed(self):
        # pop(i) while enumerating skipped whatever followed a removed entry.
        a = _StubActor(npc=True,
                       npc_senses="blindsight 10 ft., darkvision 60 ft., passive Perception 13")
        senses = a.createAttributeSenses()
        assert senses["special"] == ""
        assert senses["ranges"]["blindsight"] == 10
        assert senses["ranges"]["darkvision"] == 60

    def test_special_sense_after_recognised_ones_survives(self):
        a = _StubActor(npc=True,
                       npc_senses="darkvision 120 ft., tremorsense 30 ft., keen hearing")
        assert a.createAttributeSenses()["special"] == "keen hearing"


class TestCharacterSenses(object):
    """B044: the PC branch did not exist -- everything returned 0."""

    def test_token_night_vision_becomes_darkvision(self):
        a = _StubActor(token=_pc_token(dim=60))
        assert a.createAttributeSenses()["ranges"]["darkvision"] == 60

    def test_bright_vision_counts_too(self):
        a = _StubActor(token=_pc_token(dim=0, bright=30))
        assert a.createAttributeSenses()["ranges"]["darkvision"] == 30

    def test_token_without_sight_grants_nothing(self):
        a = _StubActor(token=_pc_token(dim=60, has_vision=False))
        assert a.createAttributeSenses()["ranges"]["darkvision"] == 0

    def test_one_foot_sentinel_is_not_a_sense(self):
        # setupLighting stores 1 ft to mean "has sight but no configured radius".
        a = _StubActor(token=_pc_token(dim=1))
        assert a.createAttributeSenses()["ranges"]["darkvision"] == 0

    def test_missing_token_is_survivable(self):
        assert _StubActor(token=None).createAttributeSenses()["ranges"]["darkvision"] == 0
