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


def test_quadratic_tracks_the_curve_instead_of_its_control_point():
    path = circle_path("generic-quadratic")
    path["path"] = [["M", 0, 0], ["Q", 50, 100, 100, 0]]
    polygon, path_type, width, height = Scene.__new__(Scene).pathToPolygonList(path, 100, 100)
    assert path_type == PATH_TYPE.FREEHAND
    assert polygon[0] == (0, 0) and polygon[-1] == (100, 0)
    assert (50, 100) not in polygon
    assert (50, 50) in polygon
    assert all(y == pytest.approx(2 * (x / 100) * (1 - x / 100) * 100) for x, y in polygon)
    assert len(polygon) > 3


def test_open_cubic_is_not_closed_or_classified_as_a_circle():
    path = circle_path("generic-cubic")
    path["path"] = [["M", 0, 0], ["C", 25, 100, 75, 100, 100, 0]]
    polygon, path_type, width, height = Scene.__new__(Scene).pathToPolygonList(path, 100, 100)
    assert path_type == PATH_TYPE.FREEHAND
    assert polygon[0] == (0, 0) and polygon[-1] == (100, 0)
    assert len(polygon) > 5


@pytest.mark.parametrize("scale", [1, 2, 50 / 8.75])
def test_quadratic_flattening_has_bounded_output_pixel_error(scale):
    scene = Scene.__new__(Scene)
    scene._grid_multiplier = scale
    path = circle_path()
    path["path"] = [["M", 0, 0], ["Q", 50, 100, 100, 0]]
    polygon = scene.pathToPolygonList(path, 100, 100)[0]
    for sample in range(1001):
        fraction = sample / 1000
        point = (100 * fraction, 200 * fraction * (1 - fraction))
        distances = []
        for start, end in zip(polygon, polygon[1:]):
            delta_x, delta_y = end[0] - start[0], end[1] - start[1]
            projected = max(0, min(1, ((point[0] - start[0]) * delta_x + (point[1] - start[1]) * delta_y)
                                    / (delta_x ** 2 + delta_y ** 2)))
            distances.append(math.hypot(point[0] - start[0] - projected * delta_x,
                                        point[1] - start[1] - projected * delta_y))
        assert min(distances) * scale <= Scene.CURVE_TOLERANCE


def test_chained_quadratic_then_cubic_uses_the_quadratic_endpoint():
    path = circle_path()
    path["path"] = [["M", 0, 0], ["Q", 50, 100, 100, 0], ["C", 125, -100, 175, -100, 200, 0]]
    polygon = Scene.__new__(Scene).pathToPolygonList(path, 200, 100)[0]
    assert (100, 0) in polygon
    assert (150, -75) in polygon
    assert polygon[-1] == (200, 0)


@pytest.mark.parametrize("commands", [
    [["Q", 50, 100, 100, 0]],
    [["M", 0, 0], ["Q", 50, 100, 100]],
    [["M", 0, 0], ["Q", 50, math.inf, 100, 0]],
    [["M", 0, 0], ["C", 25, 100, 75, None, 100, 0]],
])
def test_malformed_curves_fail_instead_of_dropping_geometry(commands):
    path = circle_path()
    path["path"] = commands
    with pytest.raises(ValueError, match="incomplete curve|non-finite geometry"):
        Scene.__new__(Scene).pathToPolygonList(path, 100, 100)