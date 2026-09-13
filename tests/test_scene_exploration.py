import json
import math

import pytest

from entities.base import Entity
from entities.scenes import Scene

from conftest import FakeDatabase


def page():
    return {
        "id": "page-id",
        "name": "Test Map",
        "archived": False,
        "placement": 0,
        "snapping_increment": 1,
        "width": 10,
        "height": 10,
        "grid_type": "square",
        "showgrid": True,
        "graphics": [],
        "texts": [],
        "paths": [],
        "doors": [],
        "zorder": [],
        "thumbnail": "",
        "background_color": "#ffffff",
        "gridcolor": "#000000",
        "grid_opacity": 0.5,
        "scale_number": 5,
        "scale_units": "ft",
        "showdarkness": False,
        "adv_fow_enabled": False,
    }


def light_graphic(**overrides):
    graphic = {
        "id": "light-id",
        "layer": "walls",
        "imgsrc": "/images/dead.png",
        "left": 350,
        "top": 350,
        "width": 70,
        "height": 70,
        "rotation": 25,
        "legacy_lighting_enabled": True,
        "light_otherplayers": True,
        "light_radius": "20",
        "light_dimradius": "10",
    }
    graphic.update(overrides)
    return graphic


def make_scene(tmp_path, graphics=None, pins=None, journal=None, page_overrides=None, **arguments):
    database = FakeDatabase(str(tmp_path), {"use_original_image_urls": True, "maximum_wall_angle": 30, **arguments})
    database._converter = type("Converter", (), {
        "journal": journal,
        "name": "test-module",
        "actors": type("Actors", (), {"getById": lambda database, identifier: None})(),
    })()
    scene_page = page()
    scene_page.update(page_overrides or {})
    scene_page["graphics"] = list(graphics or [])
    scene_page["pins"] = list(pins or [])
    scene_page["zorder"] = [graphic["id"] for graphic in scene_page["graphics"]]
    scene = Scene.__new__(Scene)
    Scene.__init__(scene, database, scene_page, 0, "page-id")
    return scene.entity


def map_pin(**overrides):
    pin = {
        "id": "pin-id",
        "x": 350,
        "y": 420,
        "scale": 2,
        "link": "handout-id",
        "linkType": "handout",
        "subLink": "38. Secret Tunnel",
        "subLinkType": "headerGM",
        "title": None,
        "visibleTo": "",
        "useTextIcon": True,
        "iconText": "38",
        "shape": "teardrop",
        "bgColor": "#242424",
        "fgColor": "white",
    }
    pin.update(overrides)
    return pin


class JournalStub(object):
    def __init__(self):
        self.entry_id = Entity.normalizeID("handout-id")
        self.page_id = Entity.normalizeID("handout-page-id")
        self.entry = type("Entry", (), {"entity": {
            "_id": self.entry_id,
            "pages": [{"_id": self.page_id, "type": "text"}],
        }})()

    def getById(self, identifier):
        return self.entry if identifier == self.entry_id else None


def test_scene_defaults_to_token_vision_and_individual_exploration(tmp_path):
    scene = make_scene(tmp_path)

    assert scene["_stats"]["coreVersion"] == "13"
    assert scene["_stats"]["systemVersion"] == "5.3.3"
    assert scene["tokenVision"] is True
    assert scene["fog"]["mode"] == 1
    assert scene["fog"]["colors"] == {"explored": None, "unexplored": None}
    assert "exploration" not in scene["fog"]
    assert "overlay" not in scene["fog"]


def test_explicit_disable_fog_remains_available_for_world_exports(tmp_path):
    scene = make_scene(tmp_path, disable_fog=True)

    assert scene["tokenVision"] is True
    assert scene["fog"]["mode"] == 0


def test_module_exports_cannot_disable_individual_exploration(tmp_path):
    scene = make_scene(tmp_path, disable_fog=True, export_as_module=True)

    assert scene["tokenVision"] is True
    assert scene["fog"]["mode"] == 1


def test_omnidirectional_ambient_light_keeps_full_angle(tmp_path):
    scene = make_scene(tmp_path, graphics=[light_graphic(light_angle=360)])

    assert len(scene["lights"]) == 1
    assert scene["lights"][0]["config"]["angle"] == 360
    assert scene["lights"][0]["rotation"] == 25


def test_omitted_ambient_light_angle_defaults_to_full_circle(tmp_path):
    scene = make_scene(tmp_path, graphics=[light_graphic()])

    assert scene["lights"][0]["config"]["angle"] == 360


def test_directional_ambient_light_preserves_angle_and_flips_rotation(tmp_path):
    scene = make_scene(tmp_path, graphics=[light_graphic(light_angle=45)])

    assert scene["lights"][0]["config"]["angle"] == 45
    assert scene["lights"][0]["rotation"] == 205


def test_map_pin_becomes_a_linked_native_note(tmp_path):
    journal = JournalStub()
    scene = make_scene(tmp_path, pins=[map_pin()], journal=journal,
                       export_as_module=True)

    assert len(scene["notes"]) == 1
    note = scene["notes"][0]
    assert note["_id"] == Entity.normalizeID("pin-id")
    assert note["entryId"] == journal.entry_id
    assert note["pageId"] == journal.page_id
    assert note["x"] == 560
    assert note["y"] == 630
    assert note["iconSize"] == 80
    assert note["text"] == "38"
    assert note["flags"]["R20Converter"]["mapPin"]["subLink"] == "38. Secret Tunnel"
    assert note["flags"]["R20Converter"]["mapPin"]["visibleTo"] == ""


def test_map_pin_with_missing_handout_aborts_instead_of_disappearing(tmp_path):
    journal = JournalStub()
    try:
        make_scene(tmp_path, pins=[map_pin(link="missing")], journal=journal,
                   export_as_module=True)
    except ValueError as error:
        assert "Map Pin" in str(error)
    else:
        raise AssertionError("unresolved Map Pin did not abort conversion")


@pytest.mark.parametrize("snapping,multiplier", [(0, 1), (0.125, 50 / 8.75), (0.5, 50 / 35), (1, 1)])
def test_scene_scale_report_preserves_automatic_geometry(tmp_path, snapping, multiplier):
    scene = make_scene(tmp_path, graphics=[light_graphic()], page_overrides={"snapping_increment": snapping})
    original_grid = 70 * (snapping or 1)
    grid_size = int(max(50, original_grid))
    padding = math.ceil(700 * multiplier / grid_size * 0.25) * grid_size
    assert (scene["width"], scene["height"], scene["grid"]["size"]) == (int(700 * multiplier), int(700 * multiplier), grid_size)
    assert scene["lights"][0]["x"] == int(padding + 350 * multiplier)
    if multiplier == 1:
        assert "sceneScale" not in scene.get("flags", {}).get("R20Converter", {})
    else:
        report = scene["flags"]["R20Converter"]["sceneScale"]
        assert report["sourcePageId"] == "page-id"
        assert report["snappingIncrement"] == snapping
        assert report["sourceWidth"] == report["sourceHeight"] == 700
        assert report["originalGridPixels"] == original_grid
        assert report["multiplier"] == multiplier
        assert report["outputWidth"] == report["outputHeight"] == int(700 * multiplier)
        assert report["outputGridPixels"] == grid_size
        assert report["sourceGridArea"] == pytest.approx((700 / original_grid) ** 2)
        assert report["outputGridArea"] == pytest.approx((int(700 * multiplier) / grid_size) ** 2)


def test_fine_grid_warning_contains_structured_scale_report(tmp_path, monkeypatch):
    warnings = []
    monkeypatch.setattr(FakeDatabase, "logWarning", lambda database, message: warnings.append(message))
    scene = make_scene(tmp_path, page_overrides={"snapping_increment": 0.125, "name": "Renamed Fine Map"})
    warning, = [message for message in warnings if message.startswith("SCENE_SCALE ")]
    assert json.loads(warning[len("SCENE_SCALE "):]) == scene["flags"]["R20Converter"]["sceneScale"]


@pytest.mark.parametrize("snapping", [-1, -0.125, math.nan, math.inf, -math.inf, "bad-value", None])
def test_invalid_snapping_is_rejected_explicitly(tmp_path, snapping):
    with pytest.raises(ValueError, match="snapping increment"):
        make_scene(tmp_path, page_overrides={"snapping_increment": snapping})


@pytest.mark.parametrize("snapping", [0, 0.125, 0.5, 1])
def test_all_scene_surfaces_use_the_same_automatic_transform(tmp_path, monkeypatch, snapping):
    monkeypatch.setattr(Entity, "findID", lambda entity, identifier, kind: None)
    base_graphic = {"layer": "objects", "imgsrc": "https://example.invalid/image.png",
                    "left": 280, "top": 280, "width": 70, "height": 140, "rotation": 0,
                    "represents": "", "showname": False, "name": "", "fliph": False, "flipv": False,
                    "isdrawing": False, "bar1_link": "", "bar2_link": ""}
    background = dict(base_graphic, id="background", layer="map", left=350, top=350, width=700, height=700)
    tile = dict(base_graphic, id="tile")
    token = dict(base_graphic, id="token", represents="generic-actor", left=350, top=350, height=70)
    path = {"id": "wall-path", "layer": "walls", "left": 140, "top": 140,
            "width": 70, "height": 70, "rotation": 0, "scaleX": 1, "scaleY": 1,
            "path": [["M", 0, 0], ["L", 70, 70]], "fill": "transparent", "stroke": "#0000ff",
            "stroke_width": 2, "controlledby": ""}
    drawing = dict(path, id="drawing-path", layer="objects", left=210, top=210)
    text = {"id": "text", "layer": "objects", "left": 210, "top": 210, "width": 140, "height": 70,
            "rotation": 0, "text": "Scale Control", "font_family": "Signika", "font_size": 20,
            "color": "#000000", "controlledby": ""}
    scene = make_scene(tmp_path, graphics=[background, tile, token, light_graphic()],
                       page_overrides={"snapping_increment": snapping, "paths": [path, drawing], "texts": [text]})
    multiplier = max(1, 50 / (70 * (snapping or 1)))
    grid_size = max(50, 70 * (snapping or 1))
    margin = math.ceil(700 * multiplier / grid_size * 0.25) * grid_size
    transform = lambda position: int(margin + position * multiplier)
    assert scene["background"]["src"] == background["imgsrc"]
    assert scene["width"] == scene["height"] == int(700 * multiplier)
    assert (scene["tiles"][0]["x"], scene["tiles"][0]["y"]) == (transform(245), transform(210))
    assert scene["tiles"][0]["width"] == int(70 * multiplier)
    assert scene["tiles"][0]["height"] == int(140 * multiplier)
    assert (scene["tokens"][0]["x"], scene["tokens"][0]["y"]) == (transform(315), transform(315))
    assert scene["tokens"][0]["width"] * grid_size == pytest.approx(70 * multiplier)
    assert scene["walls"][0]["c"] == [transform(105), transform(105), transform(175), transform(175)]
    assert (scene["lights"][0]["x"], scene["lights"][0]["y"]) == (transform(350), transform(350))
    text_drawing, path_drawing = scene["drawings"]
    assert (text_drawing["x"], text_drawing["y"]) == (transform(140), transform(175))
    assert text_drawing["fontSize"] == pytest.approx(20 * multiplier)
    assert (path_drawing["x"], path_drawing["y"]) == (transform(175), transform(175))
    assert path_drawing["shape"]["points"] == [0, 0, int(70 * multiplier), int(70 * multiplier)]
    assert path_drawing["strokeWidth"] == pytest.approx(2 * multiplier)


@pytest.mark.parametrize("rotation", [90, 180])
@pytest.mark.parametrize("snapping", [0.125, 1])
def test_curved_walls_honor_source_rotation_and_nonuniform_scale(tmp_path, rotation, snapping):
    from test_circle_walls import circle_path
    path = circle_path("rotated-generic-curve")
    path.update({"path": [["M", 0, 0], ["Q", 50, 100, 100, 0]],
                 "layer": "walls", "left": 200, "top": 200, "width": 100, "height": 100,
                 "rotation": rotation, "scaleX": 2, "scaleY": 0.5, "stroke": "#0000ff",
                 "fill": "transparent", "stroke_width": 2, "controlledby": ""})
    scene = make_scene(tmp_path, page_overrides={"paths": [path], "snapping_increment": snapping})
    multiplier = max(1, 50 / (70 * snapping))
    grid_size = max(50, 70 * snapping)
    margin = math.ceil(700 * multiplier / grid_size * 0.25) * grid_size
    angle = math.radians(rotation)
    expected = []
    for horizontal in (-100, 100):
        expected.append([int(margin + (200 + horizontal * math.cos(angle) + 25 * math.sin(angle)) * multiplier),
                         int(margin + (200 + horizontal * math.sin(angle) - 25 * math.cos(angle)) * multiplier)])
    assert scene["walls"][0]["c"][:2] == expected[0]
    assert scene["walls"][-1]["c"][2:] == expected[1]