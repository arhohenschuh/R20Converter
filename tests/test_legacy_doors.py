"""B058: legacy Roll20 doors were not recognised at conversion time.

Roll20's legacy dynamic lighting had no door objects -- a door was a wall drawn in a
different stroke colour. Recognising that required `--auto-doors`, which the GUI
defaults ON (`client/src/components/AdvancedOptions.vue`: `autoDoors: true`) and the
CLI defaults OFF, so the same campaign kept or lost its doors depending on which one
was run.

The hash-pinned official-module baseline contains 155 legacy-colour pages among 314
walled pages. Frequency ranking is unsafe: Dragon Heist's Theater pages contain 195
orange door segments but only 146 blue wall segments, so rank 2 selects blue as doors.

The fix derives the encoding from the page instead of being told, because blanket
colour classification is unsafe on modules that already carry door objects.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import entities.scenes as scenes


class FakeScene(object):
    shouldClassifyDoorsByColour = scenes.Scene.shouldClassifyDoorsByColour
    inferDoorColors = scenes.Scene.inferDoorColors
    normalizeWallStroke = staticmethod(scenes.Scene.normalizeWallStroke)
    assertDoorConservation = staticmethod(scenes.Scene.assertDoorConservation)
    LEGACY_DOOR_COLOR = scenes.Scene.LEGACY_DOOR_COLOR

    def __init__(self, **arguments):
        self._arguments = arguments

    def getArgument(self, name, default=None):
        return self._arguments.get(name, default)


# Verbatim shapes from the archived exports.
CASSALANTER = {"name": "Cassalanter Villa", "doors": []}                 # 0 native, #0000ff + #ff9900
ASMODEUS = {"name": "Temple of Asmodeus", "doors": []}                   # 0 native, #0000ff + #ff9900
TWISTED_CAVERNS = {"name": "Level 4: Twisted Caverns", "doors": []}      # 0 native, inside DotMM
HRAKHAMAR = {"name": "Hrakhamar", "doors": [{"id": "d%d" % i} for i in range(10)]}
CRYSTAL_LABYRINTH = {"name": "Level 16: Crystal Labyrinth",
                     "doors": [{"id": "d%d" % i} for i in range(55)]}
SARGAUTH = {"name": "Level 3: Sargauth Level", "doors": [{"id": "d%d" % i} for i in range(104)]}

THEATER = {"#ff9900": 195, "#0000ff": 146}
HIDDEN_SHRINE = {"#0000ff": 272, "#00ff00": 1, "#ff9900": 1}
SUNLESS_FORTRESS = {"#0000ff": 473, "#ff9900": 59, "transparent": 40}
WINDMILL = {"#0000ff": 316, "#ff9900": 11, "#e69138": 5}


class TestLegacyPagesAreClassified(object):
    """No door objects means the doors can only be in the colours."""

    @pytest.mark.parametrize("page", [CASSALANTER, ASMODEUS, TWISTED_CAVERNS])
    def test_a_page_without_door_objects_is_classified(self, page):
        assert FakeScene().shouldClassifyDoorsByColour(page, None) is True

    def test_no_flag_is_needed_any_more(self):
        # The whole defect: this used to require --auto-doors and the CLI never set it.
        assert FakeScene(auto_doors=False).shouldClassifyDoorsByColour(CASSALANTER, None) is True

    def test_a_page_with_an_absent_doors_key_is_classified(self):
        assert FakeScene().shouldClassifyDoorsByColour({"name": "legacy"}, None) is True

    def test_a_null_doors_value_is_treated_as_absent(self):
        assert FakeScene().shouldClassifyDoorsByColour({"doors": None}, None) is True


class TestPagesWithRealDoorsAreLeftAlone(object):
    """The other half of B058: blanket classification invents doors."""

    @pytest.mark.parametrize("page", [HRAKHAMAR, SARGAUTH, CRYSTAL_LABYRINTH])
    def test_native_doors_win(self, page):
        assert FakeScene().shouldClassifyDoorsByColour(page, None) is False

    def test_the_crystal_labyrinth(self):
        # 55 door objects and five wall colours. Classifying would have turned 39 green
        # and 1 black segments into secret doors.
        assert FakeScene(auto_doors=True).shouldClassifyDoorsByColour(CRYSTAL_LABYRINTH, None) is False

    @pytest.mark.parametrize("page", [HRAKHAMAR, SARGAUTH, CRYSTAL_LABYRINTH])
    def test_native_pages_never_infer_residue(self, page):
        assert FakeScene().inferDoorColors(page, {"#0000ff": 100, "#ff9900": 12}) == (None, [])


class TestOneCampaignCanMixBothEncodings(object):
    def test_dungeon_of_the_mad_mage(self):
        # Measured: 20 pages carry door objects, Twisted Caverns carries none.
        assert FakeScene().shouldClassifyDoorsByColour(SARGAUTH, None) is False
        assert FakeScene().shouldClassifyDoorsByColour(TWISTED_CAVERNS, None) is True


class TestExplicitInstructionsWin(object):
    def test_an_explicit_door_colour_disables_inference(self):
        assert FakeScene().shouldClassifyDoorsByColour(CASSALANTER, "#ff9900") is False

    def test_no_auto_doors_disables_inference_everywhere(self):
        assert FakeScene(no_auto_doors=True).shouldClassifyDoorsByColour(CASSALANTER, None) is False
        assert FakeScene(no_auto_doors=True).shouldClassifyDoorsByColour(TWISTED_CAVERNS, None) is False


class TestCanonicalDoorColour(object):
    @pytest.mark.parametrize("colours", [THEATER, HIDDEN_SHRINE, SUNLESS_FORTRESS, WINDMILL])
    def test_orange_wins_regardless_of_frequency_or_extra_colours(self, colours):
        assert FakeScene().inferDoorColors(CASSALANTER, colours) == ("#ff9900", [])

    def test_theater_does_not_invert_walls_and_doors(self):
        door, secrets = FakeScene().inferDoorColors(CASSALANTER, THEATER)
        assert door == "#ff9900"
        assert door != "#0000ff"
        assert secrets == []

    def test_hidden_shrine_tie_does_not_create_a_secret_door(self):
        assert FakeScene().inferDoorColors(CASSALANTER, HIDDEN_SHRINE) == ("#ff9900", [])

    def test_transparent_and_near_orange_are_never_secret_doors(self):
        assert FakeScene().inferDoorColors(CASSALANTER, SUNLESS_FORTRESS)[1] == []
        assert FakeScene().inferDoorColors(CASSALANTER, WINDMILL)[1] == []

    def test_unknown_custom_palette_is_not_guessed(self):
        assert FakeScene().inferDoorColors(CASSALANTER, {"#0000ff": 100, "#ff00ff": 20}) == (None, [])


class TestStrokeNormalisation(object):
    @pytest.mark.parametrize("raw,expected", [
        ("#00f", "#0000ff"),
        ("#FF9900", "#ff9900"),
        ("rgb(0,0,255)", "#0000ff"),
        ("rgb(0, 0, 255)", "#0000ff"),
        ("rgba(255, 153, 0, 0.5)", "#ff9900"),
        ("transparent", "transparent"),
    ])
    def test_equivalent_tokens_compare_equal(self, raw, expected):
        assert FakeScene.normalizeWallStroke(raw) == expected

    def test_rgb_orange_is_detected(self):
        assert FakeScene().inferDoorColors(CASSALANTER, {"#0000ff": 100, "rgb(255, 153, 0)": 10}) == ("#ff9900", [])


class TestDoorConservation(object):
    def test_matching_post_cleanup_counts_pass(self):
        walls = [{"door": 1}, {"door": 1}, {"door": 2}, {"door": 0}]
        assert FakeScene.assertDoorConservation(walls, {1: 2, 2: 1}, "Map") == {1: 2, 2: 1}

    def test_a_dropped_classified_door_fails_closed(self):
        with pytest.raises(ValueError, match="Door conservation failed on page 'Map'"):
            FakeScene.assertDoorConservation([{"door": 1}], {1: 2, 2: 0}, "Map")
