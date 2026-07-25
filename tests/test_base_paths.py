"""Tests for the asset path helpers in :mod:`entities.base`.

These are the highest-risk pure functions in the project: they decide where
every downloaded image lands on disk, and they are the boundary where untrusted
names from the Roll20 export become real filesystem paths.
"""

import os

import pytest

from entities.base import Entity


class TestUrlsafe(object):
    def test_spaces_become_underscores(self):
        assert Entity.urlsafe("my map.png") == "my_map.png"

    def test_forward_slashes_are_preserved_as_separators(self):
        assert Entity.urlsafe("scenes/my map.png") == "scenes/my_map.png"

    def test_percent_encoding_is_rewritten_to_underscores(self):
        # A literal '%' would be re-interpreted by Foundry when it resolves the
        # path as a URL, so quote() output is defused into '_XX'.
        assert "%" not in Entity.urlsafe("100%_cotton.png")

    def test_parent_directory_sequences_are_neutralised(self):
        assert ".." not in Entity.urlsafe("../../etc/passwd")


class TestFixImageUrl(object):
    def test_empty_url_is_passed_through(self, entity):
        assert entity.fixImageUrl("") == ""

    def test_relative_urls_are_made_absolute_against_roll20(self, entity):
        assert entity.fixImageUrl("images/foo.png") == "https://app.roll20.net/images/foo.png"

    @pytest.mark.parametrize("size", ["thumb", "med", "max"])
    def test_sized_variants_are_upgraded_to_original(self, entity, size):
        url = "https://s3.amazonaws.com/files.d20.io/images/1/%s.png" % size
        assert entity.fixImageUrl(url).endswith("/original.png")

    def test_already_original_url_is_unchanged(self, entity):
        url = "https://s3.amazonaws.com/files.d20.io/images/1/original.png"
        assert entity.fixImageUrl(url) == url


class TestGetDestinationPaths(object):
    def test_returns_path_inside_the_output_directory(self, entity, tmp_path):
        dest, config = entity.getDestinationPaths("scenes/map.png")
        assert dest.startswith(str(tmp_path).replace(os.path.sep, "/"))
        assert config.endswith("/scenes/map.png")

    def test_config_path_always_uses_forward_slashes(self, entity):
        _, config = entity.getDestinationPaths("scenes/map.png")
        assert "\\" not in config

    def test_collisions_get_a_numeric_suffix(self, entity):
        first, _ = entity.getDestinationPaths("scenes/map.png")
        open(first, "wb").close()
        second, _ = entity.getDestinationPaths("scenes/map.png")
        assert first != second
        assert "map_1.png" in second

    def test_duplicate_and_edge_spaces_are_collapsed(self, entity):
        _, config = entity.getDestinationPaths("scenes/  my   map .png")
        # Runs of spaces collapse to one, and the remaining spaces become
        # underscores. Only the whole string is stripped, not each path segment,
        # so the space after "scenes/" survives as a single underscore.
        assert config.endswith("/scenes/_my_map_.png")

    def test_dedup_hashes_the_url_into_the_assets_directory(self, entity):
        url = "https://example.invalid/a.png"
        first, config = entity.getDestinationPaths("scenes/one.png", url=url, dedup=True)
        second, _ = entity.getDestinationPaths("scenes/two.png", url=url, dedup=True)
        # Same URL must resolve to the same file regardless of the entity name.
        assert first == second
        assert "/assets/" in config

    def test_dedup_separates_by_type_subdirectory(self, entity):
        url = "https://example.invalid/a.png"
        _, config = entity.getDestinationPaths("x.png", url=url, type="tokens", dedup=True)
        assert "/assets/tokens/" in config

    def test_overlong_paths_fall_back_to_the_assets_directory(self, entity):
        entity._database._arguments["max_path"] = 80
        deep = "/".join(["a" * 30] * 5) + "/map.png"
        _, config = entity.getDestinationPaths(deep)
        assert "/assets/" in config

    def test_destination_escaping_the_output_directory_is_rejected(self, entity, tmp_path):
        # urlsafe() should already have defused this; the guard is the backstop
        # that keeps a future regression there from writing outside the world.
        outside = os.path.join(os.path.dirname(str(tmp_path)), "escaped.png")
        with pytest.raises(ValueError):
            entity._assertWithinOutputDirectory(outside)

    def test_destination_inside_the_output_directory_is_accepted(self, entity, tmp_path):
        entity._assertWithinOutputDirectory(os.path.join(str(tmp_path), "ok.png"))
