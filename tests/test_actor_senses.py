"""Regression tests for actor senses (B044).

dnd5e 5.3 moved the flat sense keys into a ``ranges`` mapping
(``module/data/shared/senses-field.mjs``); the flat shape only survives via a
shim removed in 6.1. Player characters were also skipped entirely, so every PC
converted with darkvision 0 and vision modules -- which read the actor's senses,
not the token's sight range -- granted them nothing.
"""

from entities.actors import Actor


class _StubActor(object):
    """Exercises the senses builder without constructing a whole campaign."""

    createAttributeSenses = Actor.createAttributeSenses
    # re-wrap: Actor.getRaceDarkvision is already unwrapped by the staticmethod
    # descriptor at class-body time, so a plain assignment here would silently
    # turn it back into a bound instance method and break on the extra `self`.
    getRaceDarkvision = staticmethod(Actor.getRaceDarkvision)

    def __init__(self, npc=False, npc_senses="", race=""):
        self._npc = npc
        self._npc_senses = npc_senses
        self._race = race

    def isNPC(self):
        return self._npc

    def getAttribute(self, name, default=""):
        if name == "npc_senses":
            return (self._npc_senses, None, None)
        if name == "race_display":
            return (self._race, None, None)
        return (default, None, None)


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
    """B044: the PC branch did not exist -- everything returned 0.

    The first fix (1.7.0) derived darkvision from the token's own night-vision
    radius. That was measured unsound before it ever shipped to a user: a High
    Elf in the reference campaign carries a 5 ft token radius against the 60 ft
    the race actually grants. The race name is the only signal that is actually
    grounded in the rules, so it is the only one used now.
    """

    def test_elf_gets_standard_darkvision(self):
        assert _StubActor(race="High Elf").createAttributeSenses()["ranges"]["darkvision"] == 60

    def test_half_elf_gets_standard_darkvision(self):
        assert _StubActor(race="Half-Elf").createAttributeSenses()["ranges"]["darkvision"] == 60

    def test_drow_gets_superior_darkvision(self):
        assert _StubActor(race="Drow").createAttributeSenses()["ranges"]["darkvision"] == 120

    def test_dwarf_gets_standard_darkvision(self):
        assert _StubActor(race="Hill Dwarf").createAttributeSenses()["ranges"]["darkvision"] == 60

    def test_human_has_no_darkvision(self):
        assert _StubActor(race="Standard Human").createAttributeSenses()["ranges"]["darkvision"] == 0

    def test_variant_human_has_no_darkvision(self):
        assert _StubActor(race="Variant Human").createAttributeSenses()["ranges"]["darkvision"] == 0

    def test_dragonborn_has_no_darkvision(self):
        assert _StubActor(race="Dragonborn").createAttributeSenses()["ranges"]["darkvision"] == 0

    def test_unrecognised_race_declines_to_guess(self):
        # Homebrew or a name the table does not cover: 0, not a guess.
        assert _StubActor(race="Warforged").createAttributeSenses()["ranges"]["darkvision"] == 0

    def test_empty_race_declines_to_guess(self):
        assert _StubActor(race="").createAttributeSenses()["ranges"]["darkvision"] == 0


class TestRaceDarkvisionTable(object):
    """Direct coverage of the lookup, including the ordering trap."""

    def test_drow_beats_the_generic_elf_pattern(self):
        # "Drow" contains no literal "elf", but "Dark Elf" does -- and must still
        # resolve to superior darkvision, not the generic elf entry.
        assert Actor.getRaceDarkvision("Dark Elf") == 120

    def test_gnome_gets_standard_darkvision(self):
        assert Actor.getRaceDarkvision("Rock Gnome") == 60

    def test_half_orc_gets_standard_darkvision(self):
        assert Actor.getRaceDarkvision("Half-Orc") == 60

    def test_tiefling_gets_standard_darkvision(self):
        assert Actor.getRaceDarkvision("Tiefling") == 60

    def test_halfling_has_no_darkvision(self):
        assert Actor.getRaceDarkvision("Lightfoot Halfling") == 0

    def test_unrecognised_name_returns_none(self):
        assert Actor.getRaceDarkvision("Warforged") is None

    def test_blank_name_returns_none(self):
        assert Actor.getRaceDarkvision("   ") is None
