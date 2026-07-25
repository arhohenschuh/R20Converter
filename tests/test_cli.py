"""Tests for the command line interface in :mod:`main`.

``main`` builds its parser at import time and only converts under
``if __name__ == "__main__"``, so importing it is side-effect free and the
parser can be exercised directly.
"""

import pytest


@pytest.fixture(scope="module")
def parser():
    import main
    return main.parser


@pytest.fixture(scope="module")
def defaultFolders():
    import main
    return main.DEFAULT_FOLDERS_AS_ITEMS


def parse(parser, *argv):
    return parser.parse_args(["world-dir", "campaign.zip"] + list(argv))


class TestFogOptions(object):
    def test_enable_fog_alone_is_accepted(self, parser):
        assert parse(parser, "--enable-fog").enable_fog is True

    def test_disable_fog_alone_is_accepted(self, parser):
        assert parse(parser, "--disable-fog").disable_fog is True

    def test_both_together_are_rejected(self, parser):
        # They are direct opposites; accepting both left the precedence
        # undefined and silently produced one of two different worlds.
        with pytest.raises(SystemExit):
            parse(parser, "--enable-fog", "--disable-fog")


class TestFolderAsItems(object):
    def test_parser_default_is_empty(self, parser):
        # argparse's "append" action appends to its default, so the default must
        # stay empty; main applies DEFAULT_FOLDERS_AS_ITEMS after parsing.
        assert parse(parser).folder_as_items == []

    def test_user_values_replace_rather_than_extend_the_default(self, parser, defaultFolders):
        args = parse(parser, "--folder-as-items", "Spells")
        assert args.folder_as_items == ["Spells"]
        assert defaultFolders == ["Magic Items"]

    def test_option_can_be_repeated(self, parser):
        args = parse(parser, "--folder-as-items", "Spells", "--folder-as-items", "Potions")
        assert args.folder_as_items == ["Spells", "Potions"]


class TestModuleOptions(object):
    @pytest.mark.parametrize("name", ["journal", "actors", "scenes", "playlists",
                                      "tables", "decks", "items"])
    def test_every_disable_module_option_exists(self, parser, name):
        # --disable-module-items was honoured by the converter but never
        # declared, so it was unreachable from the command line.
        args = parse(parser, "--disable-module-%s" % name)
        assert getattr(args, "disable_module_%s" % name) is True


class TestDefaults(object):
    def test_conversion_defaults_are_conservative(self, parser):
        args = parse(parser)
        assert args.export_as_module is False
        assert args.overwrite is False
        assert args.use_original_image_urls is False
        assert args.game_system == "dnd5e"
        assert args.max_path == 256
        assert args.assets_directory == "assets"

    def test_positional_arguments_are_required(self, parser):
        with pytest.raises(SystemExit):
            parser.parse_args([])
