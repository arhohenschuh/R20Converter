"""Regression tests for token vision arcs (B045) and actor senses (B044)."""

from entities.actors import Token, FULL_ANGLE


def _token(**overrides):
    data = {"legacy_lighting_enabled": False}
    data.update(overrides)
    return data


class TestSightAngle(object):
    """B045: Roll20 says "unlimited" by omitting the limit; Foundry reads 0 as blind."""

    def test_no_field_of_vision_limit_is_full_circle(self):
        assert Token.sightAngle(_token()) == FULL_ANGLE

    def test_explicit_limit_is_preserved(self):
        assert Token.sightAngle(_token(has_limit_field_of_vision=True,
                                       limit_field_of_vision_total=90)) == 90

    def test_legacy_token_without_losangle_is_full_circle(self):
        assert Token.sightAngle(_token(legacy_lighting_enabled=True)) == FULL_ANGLE

    def test_legacy_zero_losangle_is_full_circle(self):
        assert Token.sightAngle(_token(legacy_lighting_enabled=True,
                                       light_losangle=0)) == FULL_ANGLE

    def test_unparseable_angle_falls_back_to_full_circle(self):
        assert Token.sightAngle(_token(has_limit_field_of_vision=True,
                                       limit_field_of_vision_total="wide")) == FULL_ANGLE

    def test_out_of_range_angle_falls_back_to_full_circle(self):
        assert Token.sightAngle(_token(has_limit_field_of_vision=True,
                                       limit_field_of_vision_total=999)) == FULL_ANGLE

    def test_never_emits_a_zero_degree_cone(self):
        cases = [_token(),
                 _token(legacy_lighting_enabled=True),
                 _token(has_limit_field_of_vision=True, limit_field_of_vision_total=0),
                 _token(has_limit_field_of_vision=True, limit_field_of_vision_total=-5)]
        assert all(Token.sightAngle(t) != 0 for t in cases)


class TestLightAngle(object):
    """The same defect on the emitted-light arc."""

    def test_no_directional_light_is_full_circle(self):
        assert Token.lightAngle(_token()) == FULL_ANGLE

    def test_explicit_directional_angle_is_preserved(self):
        assert Token.lightAngle(_token(has_directional_bright_light=True,
                                       directional_bright_light_total=45)) == 45

    def test_legacy_without_angle_is_full_circle(self):
        assert Token.lightAngle(_token(legacy_lighting_enabled=True)) == FULL_ANGLE

    def test_unparseable_angle_falls_back_to_full_circle(self):
        assert Token.lightAngle(_token(has_directional_bright_light=True,
                                       directional_bright_light_total=None)) == FULL_ANGLE


class TestTokenDefaults(object):
    def test_token_without_roll20_data_is_not_blind(self):
        t = Token("id", "Somebody", None)
        assert t.sight_angle == FULL_ANGLE
        assert t.light_angle == FULL_ANGLE

    def test_emitted_token_declares_a_full_arc(self):
        t = Token("id", "Somebody", None)
        d = t.getDict()
        assert d["sight"]["angle"] == FULL_ANGLE
        assert d["light"]["angle"] == FULL_ANGLE

    def test_full_arc_does_not_trigger_the_rotation_flip(self):
        # The 180-degree flip only applies to a narrowed cone.
        t = Token("id", "Somebody", None)
        t.rotation = 90
        assert t.getDict()["rotation"] == 90

    def test_narrow_cone_still_triggers_the_rotation_flip(self):
        t = Token("id", "Somebody", None)
        t.rotation = 90
        t.sight_angle = 60
        assert t.getDict()["rotation"] == 270
