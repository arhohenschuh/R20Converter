"""Tests for :mod:`utils` and :mod:`messages`."""

import json
import os

import pytest

import messages
import utils


class TestGetFVTTDataPath(object):
    @pytest.fixture(autouse=True)
    def isolate_environment(self, monkeypatch):
        # getFVTTDataPath reads several environment variables and falls back to
        # the home directory, so every test starts from a known-empty state.
        for name in ("FOUNDRY_VTT_DATA_PATH", "LOCALAPPDATA", "XDG_DATA_HOME"):
            monkeypatch.delenv(name, raising=False)

    def test_explicit_environment_variable_wins(self, monkeypatch, tmp_path):
        monkeypatch.setenv("FOUNDRY_VTT_DATA_PATH", str(tmp_path))
        assert utils.getFVTTDataPath() == str(tmp_path)

    def test_options_json_data_path_overrides_the_default(self, monkeypatch, tmp_path):
        # A Foundry install can be told to keep its data elsewhere; that
        # redirection lives in Config/options.json and must be honoured.
        config = tmp_path / "Config"
        config.mkdir()
        elsewhere = str(tmp_path / "elsewhere")
        (config / "options.json").write_text(json.dumps({"dataPath": elsewhere}))
        monkeypatch.setenv("FOUNDRY_VTT_DATA_PATH", str(tmp_path))
        assert utils.getFVTTDataPath() == elsewhere

    def test_unreadable_options_json_falls_back_to_the_base_path(self, monkeypatch, tmp_path):
        config = tmp_path / "Config"
        config.mkdir()
        (config / "options.json").write_text("this is not json")
        monkeypatch.setenv("FOUNDRY_VTT_DATA_PATH", str(tmp_path))
        assert utils.getFVTTDataPath() == str(tmp_path)

    def test_platform_default_is_used_when_unset(self, monkeypatch, tmp_path):
        monkeypatch.setattr(utils.platform, "system", lambda: "Windows")
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        assert utils.getFVTTDataPath() == os.path.join(str(tmp_path), "FoundryVTT")


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
