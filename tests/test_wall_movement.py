"""B057: converted walls did not restrict movement.

`move` was derived from Roll20's page-level `lightrestrictmove`. Measured across the
24 archived exports that field is `true` on 52 pages and `null` on 616 -- and never
once `false`. It is a legacy field Jumpgate no longer maintains, so 136,884 of
248,169 wall segments converted with `move: 0`: purple in Foundry, and tokens walk
straight through them.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import entities.scenes as scenes


class FakeScene(object):
    """Only the argument lookup matters to `wallMovementRestriction`."""

    wallMovementRestriction = scenes.Scene.wallMovementRestriction

    def __init__(self, **arguments):
        self._arguments = arguments

    def getArgument(self, name, default=None):
        return self._arguments.get(name, default)


@pytest.fixture(autouse=True)
def jumpgate():
    previous = getattr(scenes, "release", None)
    scenes.Scenes.setRelease("jumpgate")
    yield
    scenes.Scenes.setRelease(previous)


BLOCKS = 20
PASSES = 0


class TestJumpgatePagesIgnoreTheLegacyFlag(object):
    @pytest.mark.parametrize("page", [
        {"lightrestrictmove": None},   # 616 of 668 measured pages
        {"lightrestrictmove": True},   # 52 of 668
        {},                            # key absent entirely
        {"lightrestrictmove": False},  # never observed, but must not disarm a wall
    ])
    def test_a_wall_on_the_lighting_layer_blocks_movement(self, page):
        assert FakeScene().wallMovementRestriction(page) == BLOCKS

    def test_the_wardens_page_that_started_it(self):
        # Verbatim: 72 of 79 Wardens pages carry exactly this.
        assert FakeScene().wallMovementRestriction({"lightrestrictmove": None}) == BLOCKS


class TestLegacyCampaignsCanStillSayNo(object):
    @pytest.fixture(autouse=True)
    def legacy(self):
        scenes.Scenes.setRelease("legacy")
        yield

    def test_an_explicit_false_is_honoured(self):
        assert FakeScene().wallMovementRestriction({"lightrestrictmove": False}) == PASSES

    @pytest.mark.parametrize("page", [{"lightrestrictmove": None}, {}])
    def test_unset_is_not_a_no(self, page):
        # The bug in one line: `null` was read as "the GM turned movement off".
        assert FakeScene().wallMovementRestriction(page) == BLOCKS


class TestExplicitOverrides(object):
    def test_no_restrict_movement_wins(self):
        assert FakeScene(no_restrict_movement=True).wallMovementRestriction({"lightrestrictmove": True}) == PASSES

    def test_restrict_movement_still_forces_blocking(self):
        scenes.Scenes.setRelease("legacy")
        assert FakeScene(restrict_movement=True).wallMovementRestriction({"lightrestrictmove": False}) == BLOCKS
