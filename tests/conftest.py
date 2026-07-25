"""Shared pytest fixtures and import setup.

``src/`` is not an installable package -- the application runs as
``python3 src/main.py`` with ``src`` as the script directory, so its modules
import each other by bare name (``from version import version``). Tests
reproduce that by putting ``src`` on ``sys.path``.
"""

import os
import sys

import pytest

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)


class FakeDatabase(object):
    """Minimal stand-in for :class:`entities.base.DatabaseFile`.

    ``Entity`` only reaches into its database for the output path, the argument
    lookup and logging, so tests can supply those three things directly instead
    of constructing a whole converter and campaign.
    """

    def __init__(self, path, arguments=None):
        self._path = path
        self._arguments = arguments or {}
        self._converter = None
        self.warnings = []

    def getArgument(self, name, default=None):
        return self._arguments.get(name, default)

    def logInfo(self, msg):
        pass

    def logWarning(self, msg):
        self.warnings.append(msg)

    def logError(self, msg):
        self.warnings.append(msg)


@pytest.fixture
def entity(tmp_path):
    """An :class:`Entity` whose output directory is a fresh temp directory."""
    from entities.base import Entity

    ent = Entity.__new__(Entity)
    ent._database = FakeDatabase(str(tmp_path))
    ent._converter = None
    return ent
