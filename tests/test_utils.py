"""Tests for :mod:`utils` and :mod:`messages`."""

import json
import os

import pytest

import messages
import utils


def makeDataPath(root, system="dnd5e"):
    """A directory shaped like a Foundry user-data directory."""
    systems = root / "Data" / "systems" / system
    systems.mkdir(parents=True)
    (systems / "system.json").write_text("{}")
    return str(root)


def makeInstall(root, data_path):
    """An installation directory whose Config/options.json names ``data_path``."""
    config = root / "Config"
    config.mkdir(parents=True)
    (config / "options.json").write_text(json.dumps({"dataPath": data_path}))
    return str(root)


class TestGetFVTTDataPath(object):
    @pytest.fixture(autouse=True)
    def isolate_environment(self, monkeypatch):
        # getFVTTDataPath reads several environment variables and falls back to
        # the home directory, so every test starts from a known-empty state.
        for name in ("FOUNDRY_VTT_DATA_PATH", "LOCALAPPDATA", "XDG_DATA_HOME"):
            monkeypatch.delenv(name, raising=False)

    def test_explicit_environment_variable_wins(self, monkeypatch, tmp_path):
        data = makeDataPath(tmp_path)
        monkeypatch.setenv("FOUNDRY_VTT_DATA_PATH", data)
        assert utils.getFVTTDataPath() == data

    def test_options_json_data_path_overrides_the_default(self, monkeypatch, tmp_path):
        # A Foundry install can be told to keep its data elsewhere; that
        # redirection lives in Config/options.json and must be honoured.
        elsewhere = makeDataPath(tmp_path / "elsewhere")
        install = makeInstall(tmp_path / "install", elsewhere)
        monkeypatch.setenv("FOUNDRY_VTT_DATA_PATH", install)
        assert utils.getFVTTDataPath() == elsewhere

    def test_a_stale_data_path_is_not_accepted(self, monkeypatch, tmp_path):
        # An options.json copied from another machine names a path that does
        # not exist here. Following it silently is how a conversion ends up with
        # no compendium enrichment and no explanation.
        install = makeInstall(tmp_path / "install", str(tmp_path / "gone"))
        monkeypatch.setenv("FOUNDRY_VTT_DATA_PATH", install)
        assert utils.getFVTTDataPath() != str(tmp_path / "gone")

    def test_a_default_install_holding_no_systems_is_not_accepted(self, monkeypatch, tmp_path):
        # The real case: a default install whose options.json points at itself
        # while the data lives with a portable copy elsewhere.
        empty = tmp_path / "AppData" / "FoundryVTT"
        empty.mkdir(parents=True)
        makeInstall(empty, str(empty))
        real = makeDataPath(tmp_path / "portable-data")
        monkeypatch.setattr(utils.platform, "system", lambda: "Windows")
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData"))
        assert utils.getFVTTDataPath() != real  # it cannot guess the portable path
        assert not utils.isFVTTDataPath(utils.getFVTTDataPath())

    def test_unreadable_options_json_falls_back_to_the_base_path(self, monkeypatch, tmp_path):
        data = makeDataPath(tmp_path)
        config = tmp_path / "Config"
        config.mkdir()
        (config / "options.json").write_text("this is not json")
        monkeypatch.setenv("FOUNDRY_VTT_DATA_PATH", data)
        assert utils.getFVTTDataPath() == data

    def test_platform_default_is_named_even_when_unusable(self, monkeypatch, tmp_path):
        # Returning it anyway gives the caller something to name in the warning.
        monkeypatch.setattr(utils.platform, "system", lambda: "Windows")
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        assert utils.getFVTTDataPath() == os.path.join(str(tmp_path), "FoundryVTT")


class TestResolveFVTTDataPath(object):
    def test_a_data_directory_resolves_to_itself(self, tmp_path):
        data = makeDataPath(tmp_path)
        assert utils.resolveFVTTDataPath(data) == data

    def test_options_json_wins_over_a_local_data_tree(self, tmp_path):
        # An install can hold its own Data tree while its config redirects
        # elsewhere. Foundry follows the config, so we must too.
        install = tmp_path / "install"
        makeDataPath(install)
        elsewhere = makeDataPath(tmp_path / "elsewhere")
        makeInstall(install, elsewhere)
        assert utils.resolveFVTTDataPath(str(install)) == elsewhere

    def test_an_installation_directory_resolves_through_its_options(self, tmp_path):
        # What a portable install looks like: config beside the app, data on
        # another drive entirely.
        data = makeDataPath(tmp_path / "user-data")
        install = makeInstall(tmp_path / "FoundryVTT-Portable", data)
        assert utils.resolveFVTTDataPath(install) == data

    def test_an_unrelated_directory_resolves_to_nothing(self, tmp_path):
        assert utils.resolveFVTTDataPath(str(tmp_path)) is None

    def test_a_relative_data_path_resolves_against_the_config_directory(self, tmp_path):
        # A portable install writes dataPath ".." meaning the folder its Config
        # sits in. Resolving that against the working directory rejects an
        # install that is perfectly good.
        install = tmp_path / "FoundryVTT-Portable"
        makeDataPath(install)
        config = install / "Config"
        config.mkdir()
        (config / "options.json").write_text(json.dumps({"dataPath": ".."}))
        assert utils.resolveFVTTDataPath(str(install)) == str(install)

    def test_no_path_resolves_to_nothing(self):
        assert utils.resolveFVTTDataPath(None) is None
        assert utils.resolveFVTTDataPath("") is None

    def test_systems_directory_is_what_makes_a_data_path(self, tmp_path):
        assert not utils.isFVTTDataPath(str(tmp_path))
        assert utils.isFVTTDataPath(makeDataPath(tmp_path))


class TestMessages(object):
    def test_error_message_includes_version_and_cause(self):
        message = messages.conversionErrorMessage("1.2.3", ValueError("bad scene"))
        assert "1.2.3" in message
        assert "bad scene" in message

    def test_error_message_accepts_a_preformatted_traceback(self):
        assert "Traceback" in messages.conversionErrorMessage("1.2.3", "Traceback (most recent call last)")

    def test_plain_success_message_uses_a_bare_url(self):
        message = messages.conversionSuccessMessage()
        assert "https://forge-vtt.com" in message
        assert "<a " not in message

    def test_html_success_message_uses_an_anchor(self):
        message = messages.conversionSuccessMessage(html=True)
        assert "<a href='https://forge-vtt.com/setup'" in message

    def test_both_flavours_carry_the_same_advice(self):
        for message in (messages.conversionSuccessMessage(),
                        messages.conversionSuccessMessage(html=True)):
            assert "Conversion completed." in message
            assert "Thank you for your support!" in message
