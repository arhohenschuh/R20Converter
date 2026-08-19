import json
from types import SimpleNamespace

from entities.settings import Setting, SettingsDB


class FakeDatabase(object):
    _converter = SimpleNamespace()


class FakeConverter(object):
    path = "."
    campaign = {}

    def getArgument(self, _name, default=None):
        return default


def test_rules_version_setting_is_stored_as_legacy_json_string():
    setting = Setting(FakeDatabase(), "dnd5e.rulesVersion", "legacy").entity
    assert setting["key"] == "dnd5e.rulesVersion"
    assert setting["value"] == json.dumps("legacy")


def test_world_settings_include_exactly_one_rules_version():
    settings = [entity.entity for entity in SettingsDB(FakeConverter()).entities]
    matches = [setting for setting in settings if setting["key"] == "dnd5e.rulesVersion"]
    assert len(matches) == 1
    assert json.loads(matches[0]["value"]) == "legacy"