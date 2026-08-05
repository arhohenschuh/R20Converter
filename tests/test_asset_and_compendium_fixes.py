"""Regression tests for the asset and compendium defects found rebuilding
*Wardens of the North* (B048, B049, B050).

All three were silent: the conversion exited 0 and the damage only showed up in
the finished world, so each test asserts the observable outcome rather than the
call sequence that produces it. No network access -- the session is stubbed.
"""

import pytest

import entities.base as base
from entities.items import Item

from test_base_download import StubResponse, StubSession, stub_session, clear_resource_cache  # noqa: F401


S3 = "https://s3.amazonaws.com/files.d20.io/images/1/original.png"
RENAMED = "https://files.d20.io/images/1/original.png"


class TestHostCandidates(object):
    """B048 -- the bucket name is the first path segment, so the current URL is
    recoverable from the old one without a lookup."""

    def test_s3_url_yields_the_renamed_host_first(self):
        assert base.Entity.hostCandidates(S3) == [RENAMED, S3]

    def test_staging_bucket_is_handled_too(self):
        url = "https://s3.amazonaws.com/files.staging.d20.io/images/2/max.png"
        assert base.Entity.hostCandidates(url) == [
            "https://files.staging.d20.io/images/2/max.png", url]

    def test_query_string_is_preserved(self):
        url = "https://s3.amazonaws.com/files.d20.io/images/1/original.png?148418"
        assert base.Entity.hostCandidates(url)[0] == RENAMED + "?148418"

    @pytest.mark.parametrize("url", [
        "https://files.d20.io/images/1/original.png",      # already renamed
        "https://example.invalid/picture.png",             # not Roll20
        "https://s3.amazonaws.com/some-other-bucket/x.png",  # unrelated bucket
    ])
    def test_unrelated_urls_are_left_alone(self, url):
        assert base.Entity.hostCandidates(url) == [url]


class TestHostFallbackRecoversArt(object):
    def test_image_is_recovered_when_only_the_new_host_answers(self, entity, stub_session):
        # The measured production case: the old host 403s for everything.
        session = stub_session({S3: StubResponse(403), RENAMED: StubResponse(200, b"PNG")})
        dest, config = entity.downloadResource(S3, "scenes/map.png")
        assert open(dest, "rb").read() == b"PNG"
        assert session.requested[0] == RENAMED, "the host that answers must be tried first"

    def test_full_resolution_is_not_sacrificed_to_the_rename(self, entity, stub_session):
        # A smaller resolution on the old host must never win over the original
        # on the new one.
        med_old = "https://s3.amazonaws.com/files.d20.io/images/1/med.png"
        stub_session({RENAMED: StubResponse(200, b"BIG"), med_old: StubResponse(200, b"SMALL")})
        dest, _ = entity.downloadResource(S3, "scenes/map.png")
        assert open(dest, "rb").read() == b"BIG"

    def test_genuinely_dead_asset_still_reports_failure(self, entity, stub_session):
        stub_session({})
        dest, config = entity.downloadResource(S3, "scenes/map.png")
        assert dest is None and config == ""


class FakeConverter(object):
    def __init__(self, members):
        self._members = members

    def getZipFile(self, filename):
        if filename not in self._members:
            raise KeyError(filename)
        return self._members[filename]


class FakeMember(object):
    def __init__(self, content):
        self._content = content

    def read(self):
        return self._content


class TestZipMissFallsBackToDownload(object):
    """B049 -- the export zip is not the only copy of an asset."""

    def test_missing_from_zip_is_downloaded_instead(self, entity, stub_session):
        entity._database._converter = FakeConverter({})
        stub_session({RENAMED: StubResponse(200, b"PNG")})
        dest, config = entity.copyZipFile(S3, "images/gone.png", "scenes/map.png")
        assert dest is not None, "a zip miss must not abandon a recoverable asset"
        assert open(dest, "rb").read() == b"PNG"
        assert config.endswith(".png")

    def test_zip_hit_does_not_hit_the_network(self, entity, stub_session):
        entity._database._converter = FakeConverter({"images/here.png": FakeMember(b"ZIP")})
        session = stub_session({RENAMED: StubResponse(200, b"NET")})
        dest, _ = entity.copyZipFile(S3, "images/here.png", "scenes/map.png")
        assert open(dest, "rb").read() == b"ZIP"
        assert session.requested == []

    def test_miss_with_no_url_still_gives_up(self, entity, stub_session):
        entity._database._converter = FakeConverter({})
        stub_session({})
        dest, config = entity.copyZipFile("", "images/gone.png", "scenes/map.png")
        assert dest is None and config == ""


class FakeCompendiumItem(object):
    def __init__(self, entity):
        self.entity = entity


def _class_document():
    return {
        "_id": "compendiumid00000",
        "name": "Cleric",
        "type": "class",
        "img": "icons/cleric.webp",
        "system": {"levels": 1, "description": {"value": "<p>A priestly champion.</p>"},
                   "advancement": [{"type": "HitPoints"}] * 18},
        "_stats": {},
    }


class TestCompendiumKeepsCharacterState(object):
    """B050 -- ``--no-compendium-overwrite`` protects template data, but must not
    discard state that describes one character."""

    def _build(self, database, custom, document=None):
        return Item.createItemFromCompendium(
            database, None, FakeCompendiumItem(document or _class_document()), custom)

    def test_class_level_survives_no_compendium_overwrite(self, entity):
        entity._database._arguments = {"no_compendium_overwrite": True}
        item = self._build(entity._database, {"levels": 10})
        assert item.entity["system"]["levels"] == 10

    def test_template_data_still_yields_to_the_compendium(self, entity):
        entity._database._arguments = {"no_compendium_overwrite": True}
        item = self._build(entity._database,
                           {"levels": 10, "description": {"value": "<p>Imported from Roll20</p>"}})
        assert item.entity["system"]["description"]["value"] == "<p>A priestly champion.</p>"
        assert len(item.entity["system"]["advancement"]) == 18

    def test_weapon_proficiency_survives(self, entity):
        entity._database._arguments = {"no_compendium_overwrite": True}
        weapon = {"_id": "c2", "name": "Longsword", "type": "weapon", "img": None,
                  "system": {"proficient": 0, "equipped": False,
                             "description": {"value": "<p>Versatile.</p>"}},
                  "_stats": {}}
        item = self._build(entity._database, {"proficient": 1, "equipped": True}, weapon)
        assert item.entity["system"]["proficient"] == 1
        assert item.entity["system"]["equipped"] is True

    def test_without_the_flag_everything_is_overwritten(self, entity):
        entity._database._arguments = {"no_compendium_overwrite": False}
        item = self._build(entity._database,
                           {"levels": 10, "description": {"value": "<p>Imported from Roll20</p>"}})
        assert item.entity["system"]["levels"] == 10
        assert item.entity["system"]["description"]["value"] == "<p>Imported from Roll20</p>"

    def test_unknown_keys_are_not_smuggled_through(self, entity):
        entity._database._arguments = {"no_compendium_overwrite": True}
        item = self._build(entity._database, {"levels": 10, "spellcasting": {"progression": "full"}})
        assert "spellcasting" not in item.entity["system"]


class TestPropertiesAlwaysEmitAnArray(object):
    """B051 -- dnd5e 3.0+ calls Array#findSplice on the raw source, so a boolean
    map throws during migration and the item fails validation, reported only as a
    console warning. Guards the normalisation that keeps current output clean."""

    def test_legacy_boolean_map_becomes_an_array_of_set_keys(self):
        import dnd5e
        out = dnd5e.properties({"amm": False, "hvy": True, "fin": False, "two": True})
        assert isinstance(out, list)
        assert set(out) == {"hvy", "two"}

    def test_an_array_passes_through(self):
        import dnd5e
        assert set(dnd5e.properties(["fin", "lgt"])) == {"fin", "lgt"}

    def test_unknown_keys_are_dropped(self):
        # An invalid property fails validation for the whole item.
        import dnd5e
        assert "notAProperty" not in dnd5e.properties({"notAProperty": True, "fin": True})

    def test_empty_input_is_an_array_not_none(self):
        import dnd5e
        for value in ({}, [], None):
            assert dnd5e.properties(value) == []


class TestClassLevelsSumToCharacterLevel(object):
    """The assertion that would have caught B050 in the converter itself: a
    level-1 and a level-4 character share proficiency +2, so proficiency alone
    is not evidence."""

    @staticmethod
    def _levels(attrs):
        classes = {}
        primary = attrs.get("class")
        if primary:
            classes[primary] = int(attrs.get("base_level") or attrs.get("level") or 1)
        for i in (1, 2, 3):
            if str(attrs.get("multiclass%d_flag" % i, "0")) != "1":
                continue
            name = attrs.get("multiclass%d" % i)
            level = int(attrs.get("multiclass%d_lvl" % i) or 0)
            if name and level:
                classes[name] = level
        return classes

    def test_single_class(self):
        attrs = {"class": "Cleric", "base_level": "10", "level": "10",
                 "multiclass1_flag": "0", "multiclass1_lvl": "1"}
        levels = self._levels(attrs)
        assert levels == {"Cleric": 10}
        assert sum(levels.values()) == int(attrs["level"])

    def test_multiclass_uses_the_flag_not_the_default_level(self):
        attrs = {"class": "Rogue", "base_level": "7", "level": "10",
                 "multiclass1_flag": "1", "multiclass1": "Warlock", "multiclass1_lvl": "3",
                 "multiclass2_flag": "0", "multiclass2": "Bard", "multiclass2_lvl": "1"}
        levels = self._levels(attrs)
        assert levels == {"Rogue": 7, "Warlock": 3}
        assert sum(levels.values()) == int(attrs["level"])
