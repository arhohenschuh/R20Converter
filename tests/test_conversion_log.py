"""The converter writes a copy of its log into the output folder (1.7.1).

Previously the log existed only on stdout (CLI) or in the Electron window (GUI),
so a finished world carried no record of what was skipped during its conversion.
"""

import os

import pytest

from R20Converter import R20Converter


class _Args(object):
    def __init__(self, path):
        self.path = path


def _converter(tmp_path, logger=None):
    """Build a converter without running __init__ -- it wants a real campaign zip."""
    c = R20Converter.__new__(R20Converter)
    c._logger = logger if logger is not None else _Collector()
    c._log_fh = None
    c._log_disabled = False
    c.path = str(tmp_path / "world")
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

    def test_output_directory_is_created_if_absent(self, tmp_path):
        c = _converter(tmp_path)
        assert not os.path.exists(c.path)
        c.logInfo("first line")
        c.closeLog()
        assert os.path.isdir(c.path)

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
        c.path = "\0invalid"          # makedirs/open both reject this
        c.logInfo("must not raise")
        assert c._log_disabled is True

    def test_logging_continues_on_the_console_after_a_file_failure(self, tmp_path):
        collector = _Collector()
        c = _converter(tmp_path, collector)
        c.path = "\0invalid"
        c.logInfo("one")
        c.logInfo("two")
        assert collector.lines == ["one", "two"]
