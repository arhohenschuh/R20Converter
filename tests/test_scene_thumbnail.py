"""Scene thumbnail conversion regressions."""

import hashlib
import os

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


def test_deduplicated_thumbnail_gets_its_own_content_hash(entity, tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (600, 400), (0, 128, 255)).save(str(source), format="PNG")
    source_bytes = source.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    content_path = tmp_path / "assets" / (source_hash + ".png")
    content_path.parent.mkdir()
    source.replace(content_path)

    scene = Scene.__new__(Scene)
    scene._database = entity._database
    scene._converter = entity._converter
    scene._database._arguments["dedup_assets"] = True

    thumbnail_path, thumbnail_config = scene.createThumbnail(
        str(content_path), "scenes/thumbs/map.png")

    assert content_path.read_bytes() == source_bytes
    assert thumbnail_path != str(content_path)
    thumbnail_bytes = open(thumbnail_path, "rb").read()
    assert hashlib.sha256(thumbnail_bytes).hexdigest() == \
        os.path.splitext(os.path.basename(thumbnail_path))[0]
    assert thumbnail_config.endswith(".png")
    with Image.open(thumbnail_path) as thumbnail:
        assert thumbnail.size == (300, 100)