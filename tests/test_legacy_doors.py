"""B058: legacy Roll20 doors were not recognised at conversion time.

Roll20's legacy dynamic lighting had no door objects -- a door was a wall drawn in a
different stroke colour. Recognising that required `--auto-doors`, which the GUI
defaults ON (`client/src/components/AdvancedOptions.vue`: `autoDoors: true`) and the
CLI defaults OFF, so the same campaign kept or lost its doors depending on which one
was run.

Measured across the archived exports: 272 of 392 walled pages carry the colour
encoding, and 11 of 22 campaigns have no door objects at all -- Waterdeep Dragon
Heist encodes doors this way on 40 of its 41 walled pages, Storm King's Thunder on
19 of 25.

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
