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


def make_scene(tmp_path, graphics=None, **arguments):
    database = FakeDatabase(str(tmp_path), {"use_original_image_urls": True, **arguments})
    scene_page = page()
    scene_page["graphics"] = list(graphics or [])
    scene_page["zorder"] = [graphic["id"] for graphic in scene_page["graphics"]]
    scene = Scene.__new__(Scene)
    Scene.__init__(scene, database, scene_page, 0, "page-id")
    return scene.entity


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