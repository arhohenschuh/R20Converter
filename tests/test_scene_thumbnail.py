"""Scene thumbnail conversion regressions."""

from PIL import Image

from entities.scenes import Scene


def test_rgba_png_under_jpg_name_becomes_a_real_jpeg(tmp_path):
    path = tmp_path / "map.jpg"
    Image.new("RGBA", (600, 400), (255, 0, 0, 128)).save(str(path), format="PNG")

    Scene.__new__(Scene).createThumbnail(str(path))

    assert path.stat().st_size > 0
    with Image.open(str(path)) as thumbnail:
        assert thumbnail.format == "JPEG"
        assert thumbnail.mode == "RGB"
        assert thumbnail.size == (300, 100)
    assert not (tmp_path / "map.jpg.thumbnail").exists()