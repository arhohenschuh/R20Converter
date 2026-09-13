"""The converter writes a copy of its log into the output folder (1.7.1).

Previously the log existed only on stdout (CLI) or in the Electron window (GUI),
so a finished world carried no record of what was skipped during its conversion.
"""

import json
import os
from types import SimpleNamespace

import pytest

import R20Converter as converter_module
from R20Converter import R20Converter
from entities.base import Entity


class _Args(object):
    def __init__(self, path):
        self.path = path


def _converter(tmp_path, logger=None, create=True):
    """Build a converter without running __init__ -- it wants a real campaign zip.

    ``create`` mirrors the state after ``convert()`` has made the output folder;
    pass False to exercise the window before that happens.
    """
    c = R20Converter.__new__(R20Converter)
    c._logger = logger if logger is not None else _Collector()
    c._log_fh = None
    c._log_disabled = False
    c._log_buffer = []
    c.path = str(tmp_path / "world")
    if create:
        os.makedirs(c.path, exist_ok=True)
    return c


class _Collector(object):
    def __init__(self):
        self.lines = []

    def logInfo(self, msg):
        self.lines.append(msg)
    logWarning = logInfo
    logError = logInfo


def _read(c):
    with open(os.path.join(c.path, R20Converter.LOG_FILENAME), encoding="utf-8") as fh:
        return fh.read()


class TestConversionLog(object):
    def test_log_file_is_written_into_the_output_folder(self, tmp_path):
        c = _converter(tmp_path)
        c.logInfo("Creating Handout : Volo")
        c.closeLog()
        assert _read(c) == "Creating Handout : Volo\n"

    def test_log_never_creates_the_output_directory(self, tmp_path):
        # Regression: the log used to makedirs(exist_ok=True) here, which ran
        # before convert()'s bare makedirs and turned every conversion into
        # FileExistsError. That bare call is also the GUI's only guard against
        # converting into an existing world, so it must stay the one to create it.
        c = _converter(tmp_path, create=False)
        c.logInfo("*** Converting Campaign 'Storm over Savage Frontier' ***")
        assert not os.path.exists(c.path)

    def test_lines_logged_before_the_directory_exists_are_not_lost(self, tmp_path):
        c = _converter(tmp_path, create=False)
        c.logInfo("logged early")
        os.makedirs(c.path)          # what convert() does next
        c.logInfo("logged later")
        c.closeLog()
        assert _read(c).splitlines() == ["logged early", "logged later"]

    def test_warnings_and_errors_are_captured_too(self, tmp_path):
        c = _converter(tmp_path)
        c.logInfo("info")
        c.logWarning("Could not find compendium item")
        c.logError("boom")
        c.closeLog()
        assert _read(c).splitlines() == ["info", "Could not find compendium item", "boom"]

    def test_console_logging_still_happens(self, tmp_path):
        collector = _Collector()
        c = _converter(tmp_path, collector)
        c.logInfo("to the console as well")
        c.closeLog()
        assert collector.lines == ["to the console as well"]

    def test_lines_are_flushed_so_a_crash_still_leaves_a_log(self, tmp_path):
        c = _converter(tmp_path)
        c.logInfo("written before the crash")
        # deliberately not closed, as an aborted run would leave it
        assert "written before the crash" in _read(c)

    def test_finish_log_appends_the_closing_message(self, tmp_path):
        c = _converter(tmp_path)
        c.logInfo("body")
        c.finishLog("\nConversion completed.\n")
        assert _read(c).endswith("Conversion completed.\n\n")

    def test_a_second_run_replaces_the_previous_log(self, tmp_path):
        c = _converter(tmp_path)
        c.logInfo("first run")
        c.closeLog()
        c2 = _converter(tmp_path)
        c2.logInfo("second run")
        c2.closeLog()
        assert "first run" not in _read(c2)

    def test_an_unwritable_path_never_breaks_the_conversion(self, tmp_path):
        c = _converter(tmp_path)
        # The directory exists, so the log gets as far as open() -- and finds a
        # directory sitting where its file should go.
        os.makedirs(os.path.join(c.path, R20Converter.LOG_FILENAME))
        c.logInfo("must not raise")
        assert c._log_disabled is True

    def test_logging_continues_on_the_console_after_a_file_failure(self, tmp_path):
        collector = _Collector()
        c = _converter(tmp_path, collector)
        os.makedirs(os.path.join(c.path, R20Converter.LOG_FILENAME))
        c.logInfo("one")
        c.logInfo("two")
        assert collector.lines == ["one", "two"]


class TestWorldInitialization(object):
    @pytest.mark.parametrize("skip_chat", [False, True])
    def test_items_exist_before_macro_and_chat_links(self, tmp_path, monkeypatch, skip_chat):
        converter = _converter(tmp_path, create=False)
        converter.campaign = {"campaign_title": "Linked World"}
        converter.getArgument = lambda name, default=None: skip_chat if name == "dont_convert_chat" else default
        converter.logAssetIdentitySummary = lambda: None
        item_databases = []

        class Database(object):
            def __init__(self, owner, *args):
                self.entities = []
                self.saved = None

            @staticmethod
            def setRelease(release):
                pass

            def save(self):
                self.saved = list(self.entities)
                return self

        class ItemDatabase(Database):
            def __init__(self, owner):
                super(ItemDatabase, self).__init__(owner)
                item_databases.append(self)

            def createEntities(self):
                self.entities.append("source-item")

        def macros(owner):
            assert owner.items.entities == ["source-item"]
            owner.items.entities.append("macro-imported-item")
            return Database(owner)

        def chat(owner):
            assert owner.items.entities == ["source-item", "macro-imported-item"]
            owner.items.entities.append("chat-imported-item")
            return Database(owner)

        for name in ("SettingsDB", "Users", "Folders", "Journal", "Actors", "Scenes",
                     "Combat", "Playlists", "Tables", "EmptyDB", "World"):
            monkeypatch.setattr(converter_module, name, Database)
        monkeypatch.setattr(converter_module, "Items", ItemDatabase)
        monkeypatch.setattr(converter_module, "Macros", macros)
        monkeypatch.setattr(converter_module, "ChatLog", chat)

        try:
            converter.convert()
        finally:
            converter.closeLog()

        assert item_databases == [converter.items]
        expected = ["source-item", "macro-imported-item"]
        if not skip_chat:
            expected.append("chat-imported-item")
        assert converter.items.saved == expected
        assert converter.cards is converter.items

    @pytest.mark.parametrize("syntax", ["html", "markdown"])
    @pytest.mark.parametrize("skip_chat", [False, True])
    def test_world_macro_compendium_links_resolve_to_one_saved_item(
            self, tmp_path, monkeypatch, syntax, skip_chat):
        data_root = tmp_path / "foundry" / "Data"
        system_root = data_root / "systems" / "dnd5e"
        system_root.mkdir(parents=True)
        (system_root / "system.json").write_text(json.dumps({
            "id": "dnd5e", "version": "5.3.3", "packs": [],
        }), encoding="utf-8")
        url = "https://roll20.net/compendium/dnd5e/Spells:Light"
        action = '<a href="%s">Light</a>' % url if syntax == "html" else "[Light](%s)" % url
        campaign = {
            "campaign_title": "World Macro Links", "release": "legacy",
            "playerspecificpages": False, "playerpageid": None, "turnorder": [],
            "players": [{"id": "-player", "d20userid": "1", "displayname": "Gamemaster",
                         "color": "#000000", "macrobar": []}],
            "journalfolder": [], "handouts": [], "characters": [], "pages": [],
            "decks": [], "rollabletables": [], "tables": [], "jukebox": [], "jukeboxfolder": [],
            "macros": [
                {"id": "-macro-first", "name": "First", "player_id": "-player",
                 "visibleto": "all", "action": action},
                [{"id": "-macro-second", "name": "Second", "player_id": "-player",
                  "visibleto": "", "action": action}],
            ],
            "chat_archive": [{"-message": {"type": "general", "content": "Kept message",
                                          "who": "Gamemaster", "playerid": "-player", ".priority": 123}}],
        }
        source = tmp_path / "campaign.json"
        source.write_text(json.dumps(campaign), encoding="utf-8")
        output = tmp_path / "world"
        donor = {
            "_id": "donorLight000001", "name": "Light", "type": "spell",
            "img": "icons/svg/light.svg", "system": {"description": {"value": "Linked spell"}},
            "effects": [],
        }
        pack_root = system_root / "packs"
        pack_root.mkdir()
        pack_name = converter_module.foundry.DND5E_SRD_PACKS["2014"]["spells"]
        (pack_root / (pack_name + ".db")).write_text(json.dumps(donor) + "\n", encoding="utf-8")
        monkeypatch.setattr(converter_module.utils, "getFVTTDataPath",
                            lambda: pytest.fail("World fixture must not discover machine-wide Foundry data"))
        converter = R20Converter(SimpleNamespace(
            path=str(output), zip_file=str(source), json=True, srd_edition="2014",
            fvtt_data_path=str(data_root.parent), dont_convert_chat=skip_chat), _Collector())
        assert converter.fvtt_path == str(data_root.parent)

        try:
            converter.convert()
        finally:
            converter.closeLog()

        def records(filename):
            return [json.loads(line) for line in (output / "data" / filename).read_text(
                encoding="utf-8").splitlines() if line]

        items = records("items.db")
        assert len(items) == 1
        assert items[0]["name"] == "Light"
        assert items[0]["system"]["description"]["value"] == "Linked spell"
        macros = records("macros.db")
        assert len(macros) == 2
        assert {macro["command"] for macro in macros} == {"@UUID[Item.%s]{Light}" % items[0]["_id"]}
        assert {macro["_id"] for macro in macros} == {
            Entity.normalizeID("-macro-first"), Entity.normalizeID("-macro-second")}
        folders = records("folders.db")
        assert any(folder["_id"] == items[0]["folder"] and folder["type"] == "Item" for folder in folders)
        if skip_chat:
            assert not (output / "data/messages.db").exists()
        else:
            messages = records("messages.db")
            assert len(messages) == 1
            assert messages[0]["content"] == "Kept message"
        assert (output / "world.json").is_file()
