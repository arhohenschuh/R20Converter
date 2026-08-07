"""B056: the stored asset extension comes from the Roll20 URL, not the content.

Two ways that produced a file Foundry silently refuses to render:
  * a cache-busting fragment after `&` survived, giving `.svg&cb=5` (52 assets
    across two exports) -- only `?` was stripped;
  * `.jfif` is a perfectly ordinary JPEG container that Roll20 serves and Foundry's
    `CONST.IMAGE_FILE_EXTENSIONS` does not list, so the Lakeside map on
    *Wardens of the North* was on disk but never drawn.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import entities.base as base


class FakeAssets(object):
    assetExtension = base.Entity.assetExtension
    RENDERABLE_EXTENSIONS = base.Entity.RENDERABLE_EXTENSIONS
    EXTENSION_ALIASES = base.Entity.EXTENSION_ALIASES


@pytest.fixture
def db():
    return FakeAssets()


class TestCacheBustingFragments(object):
    @pytest.mark.parametrize("url,expected", [
        ("https://files.d20.io/images/1/original.svg&cb=5", ".svg"),
        ("https://files.d20.io/images/1/original.png?1728463534", ".png"),
        ("https://files.d20.io/images/1/original.webp?v=2&cb=9", ".webp"),
        ("https://files.d20.io/images/1/original.gif&", ".gif"),
    ])
    def test_only_the_extension_survives(self, db, url, expected):
        assert db.assetExtension(url) == expected

    def test_an_ampersand_fragment_is_not_left_in_the_name(self, db):
        # ".svg&cb=5" is not a renderable extension, so the asset never drew.
        assert "&" not in db.assetExtension("https://x/y/original.svg&cb=5")


class TestUnrenderableAliases(object):
    @pytest.mark.parametrize("url,expected", [
        ("https://files.d20.io/images/1/original.jfif", ".jpg"),
        ("https://files.d20.io/images/1/original.JFIF", ".jpg"),
        ("https://files.d20.io/images/1/original.jpe", ".jpg"),
        ("https://files.d20.io/images/1/original.tif", ".tiff"),
    ])
    def test_alias_maps_to_something_foundry_renders(self, db, url, expected):
        assert db.assetExtension(url) == expected
        assert expected[1:] in db.RENDERABLE_EXTENSIONS

    def test_the_lakeside_map_url(self, db):
        # Verbatim from the Wardens export; stored as .jfif, so the map never drew.
        url = "https://s3.amazonaws.com/files.d20.io/images/412761649/Za_klakV4u7Z2z3HSHC8hg/med.jfif?1728463534"
        assert db.assetExtension(url) == ".jpg"


class TestOrdinaryUrlsAreUnchanged(object):
    @pytest.mark.parametrize("url,expected", [
        ("https://files.d20.io/images/1/original.png", ".png"),
        ("https://files.d20.io/images/1/original.webp", ".webp"),
        ("https://files.d20.io/images/1/original.jpg", ".jpg"),
        ("https://files.d20.io/images/1/original.svg", ".svg"),
    ])
    def test_supported_extensions_pass_through(self, db, url, expected):
        assert db.assetExtension(url) == expected

    def test_no_extension_returns_empty(self, db):
        assert db.assetExtension("https://files.d20.io/images/1/original") == ""
