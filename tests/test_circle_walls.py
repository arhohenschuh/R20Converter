"""Dynamic-layer circle Wall regressions (B076)."""

import math

import pytest

from entities.base import Entity
from entities.scenes import PATH_TYPE, Scene


class CircleScene(Scene):
    def __init__(self, **arguments):
        self.arguments = arguments

    def getArgument(self, name, default=None):
        return self.arguments.get(name, default)


def circle_path(identifier="circle-source-id"):
    return {
        "id": identifier,
        "path": [
            ["M", 0, 17],
            ["C", 0, 7.6111584, 7.6111584, 0, 17, 0],
            ["C", 26.3888416, 0, 34, 7.6111584, 34, 17],
            ["C", 34, 26.3888416, 26.3888416, 34, 17, 34],
            ["C", 7.6111584, 34, 0, 26.3888416, 0, 17],
            ["Z"],
        ],
        "points": None,
        "shape": "",
        "scaleX": 1,
        "scaleY": 1,
        "rotation": 0,
        "barrierType": "wall",
        "oneWayReversed": False,
    }


def test_four_cubic_circle_flattens_to_sixteen_closed_segments():
    scene = Scene.__new__(Scene)
    polygon, path_type, width, height = scene.pathToPolygonList(
        circle_path(), 34, 34)

    assert path_type == PATH_TYPE.CIRCLE
    assert len(polygon) == 17
    assert polygon[0] == polygon[-1]
    assert polygon[0] == (0, 17)
    assert polygon[4] == (17, 0)
    assert polygon[8] == (34, 17)
    assert polygon[12] == (17, 34)
    assert (width, height) == (34, 34)


def test_non_uniform_scale_and_rotation_are_applied_around_center():
    path = circle_path()
    path.update({"scaleX": 2, "scaleY": 1, "rotation": 90})
    point = Scene.transformPathPoint((0, 17), path, 68, 34)
    assert point[0] == pytest.approx(34)
    assert point[1] == pytest.approx(-17)


def test_one_way_circle_is_vision_only_and_has_a_stable_id():
    scene = CircleScene()
    path = circle_path("toa-circle")
    path.update({"barrierType": "oneWay", "oneWayReversed": True})
    wall = scene.createPathWall(
        path, {"lightrestrictmove": None}, PATH_TYPE.CIRCLE, 3,
        (0, 0), (1, 1), 10, 20, 2, 0)
    assert wall["_id"] == Entity.strToID("toa-circle:circle-wall:3")
    assert wall["c"] == [10, 20, 12, 22]
    assert wall["move"] == 0
    assert wall["sight"] == 20
    assert wall["dir"] == 2


def test_ordinary_circle_honors_explicit_movement_restriction():
    scene = CircleScene()
    wall = scene.createPathWall(
        circle_path(), {"lightrestrictmove": True}, PATH_TYPE.CIRCLE, 0,
        (0, 0), (1, 1), 0, 0, 1, 0)
    assert wall["move"] == 20
    assert wall["dir"] == 0


@pytest.mark.parametrize("arguments,page,expected", [
    ({"restrict_movement": True}, {"lightrestrictmove": None}, 20),
    ({"no_restrict_movement": True}, {"lightrestrictmove": True}, 0),
    ({}, {"lightrestrictmove": None}, 0),
])
def test_circle_movement_arguments_override_source_page(arguments, page, expected):
    assert CircleScene(**arguments).circleMovementRestriction(page) == expected


def test_degenerate_circle_is_rejected():
    path = circle_path()
    path["path"] = [["M", 1, 1], ["C", 1, 1, 1, 1, 1, 1], ["Z"]]
    with pytest.raises(ValueError, match="degenerate circle"):
        Scene.__new__(Scene).pathToPolygonList(path, 0, 0)


def test_exact_zero_area_jumpgate_ellipse_is_source_debris():
    path = {
        "id": "-OfdWqaRPUGfua7D38jL",
        "path": None,
        "points": [[0, 0], [0, 0]],
        "shape": "eli",
        "width": 0,
        "height": 0,
    }
    assert Scene.isZeroAreaJumpgateEllipse(path) is True


def test_two_point_jumpgate_ellipse_is_reconstructed():
    path = {
        "id": "-OfdX0FtG4sM1hLknO8q",
        "path": None,
        "points": [[0, 0], [26.25, 26.25]],
        "shape": "eli",
        "width": 0,
        "height": 0,
    }
    polygon, path_type, width, height = Scene.__new__(Scene).pathToPolygonList(
        path, path["width"], path["height"])
    assert path_type == PATH_TYPE.CIRCLE
    assert len(polygon) == 17
    assert polygon[0] == polygon[-1]
    assert polygon[0] == pytest.approx((0, 13.125))
    assert polygon[4] == pytest.approx((13.125, 0))
    assert (width, height) == pytest.approx((26.25, 26.25))


def test_non_finite_circle_is_rejected():
    path = circle_path()
    path["path"][1][1] = math.inf
    with pytest.raises(ValueError, match="non-finite geometry"):
        Scene.__new__(Scene).pathToPolygonList(path, 34, 34)