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


class FakeMember(object):
    def __init__(self, content):
        self._content = content

    def read(self):
        return self._content


class FakeConverter(object):
    """Serves zip members under the names R20Exporter actually writes."""

    def __init__(self, members):
        self._members = members
        self.requested = []
        self.misses = []

    def getZipFile(self, filename):
        self.requested.append(filename)
        if filename not in self._members:
            raise KeyError(filename)
        return self._members[filename]

    def getZipPathForUrl(self, url):
        return None

    def noteZipMiss(self, filename):
        self.misses.append(filename)


class TestAssetsCopiedOutOfTheZip(object):
    """The first B056 fix only reached ``downloadResource``. Assets that *are* in
    the export -- 139 of them across five archived campaigns -- come through
    ``copyZipFile``, which kept deriving the stored name the old way.

    The two extensions are not the same thing: R20Exporter names the zip member
    from the raw URL (its ADR-003), so the lookup must keep the raw spelling while
    the file written to disk must be renderable.
    """

    @pytest.mark.parametrize("url,member,stored", [
        ("https://files.d20.io/images/1/original.svg&cb=5", "graphics/tok.svg&cb=5", ".svg"),
        ("https://s3.amazonaws.com/files.d20.io/images/1/med.jfif?1728463534", "graphics/tok.jfif", ".jpg"),
    ])
    def test_stored_name_is_renderable_but_the_lookup_is_not_rewritten(
            self, entity, url, member, stored):
        converter = FakeConverter({member: FakeMember(b"IMG")})
        entity._database._converter = converter
        dest, config = entity.copyZipFile(url, member, "scenes/map.png")

        assert open(dest, "rb").read() == b"IMG", "the asset must still be found in the zip"
        assert converter.misses == []
        assert os.path.splitext(dest)[1] == stored
        assert os.path.splitext(config)[1] == stored
        assert stored[1:] in base.Entity.RENDERABLE_EXTENSIONS
        assert "&" not in dest

    def test_the_lakeside_map(self, entity):
        # Verbatim from the Wardens export, where the map converted and never drew.
        url = "https://s3.amazonaws.com/files.d20.io/images/412761649/Za_klakV4u7Z2z3HSHC8hg/med.jfif?1728463534"
        member = "pages/054 - Lakeside/thumbnail.jfif"
        converter = FakeConverter({member: FakeMember(b"IMG")})
        entity._database._converter = converter
        dest, _ = entity.copyZipFile(url, member, "scenes/thumb.png")
        assert dest.endswith(".jpg")

    def test_an_ordinary_asset_is_untouched(self, entity):
        url = "https://files.d20.io/images/1/original.webp"
        converter = FakeConverter({"graphics/tok.webp": FakeMember(b"IMG")})
        entity._database._converter = converter
        dest, _ = entity.copyZipFile(url, "graphics/tok.webp", "scenes/map.png")
        assert dest.endswith(".webp")

    def test_zero_byte_zip_member_falls_back_to_download(self, entity):
        url = "https://files.d20.io/images/1/original.jpg"
        converter = FakeConverter({"graphics/map.jpg": FakeMember(b"")})
        entity._database._converter = converter
        calls = []
        entity.downloadResource = lambda *args, **kwargs: calls.append(args) or \
            ("downloaded.jpg", "modules/test/assets/downloaded.jpg")
        result = entity.copyZipFile(url, "graphics/map.jpg", "scenes/map.jpg")
        assert result == ("downloaded.jpg", "modules/test/assets/downloaded.jpg")
        assert calls and calls[0][0] == url

    def test_placeholder_zip_member_falls_back_to_download(self, entity, monkeypatch):
        url = "https://files.d20.io/images/1/original.jpg"
        converter = FakeConverter({"graphics/map.jpg": FakeMember(b"DEAD")})
        entity._database._converter = converter
        monkeypatch.setattr(base, "isRoll20Placeholder",
                            lambda content: content == b"DEAD")
        calls = []
        entity.downloadResource = lambda *args, **kwargs: calls.append(args) or \
            ("downloaded.jpg", "modules/test/assets/downloaded.jpg")
        result = entity.copyZipFile(url, "graphics/map.jpg", "scenes/map.jpg")
        assert result == ("downloaded.jpg", "modules/test/assets/downloaded.jpg")
        assert calls and calls[0][0] == url

