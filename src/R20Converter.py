#!/usr/bin/python3
# -*- coding: utf-8 -*-

import json
import zipfile
import argparse
import sys
import os
import platform
from slugify import slugify
from collections import OrderedDict

import utils
import foundry
from version import version
from world import World
from module import Module
from entities import DatabaseFile, EmptyDB, \
        Actors, Items, Combat, \
        Folders, Journal, Playlists, \
        Scenes, SettingsDB, Users, \
        Tables, RollableTables, Decks, \
        Macros, ChatLog


class R20Converter(object):
    def __init__(self, args, logger=None):
        self._logger = utils if logger is None else logger
        self.args = args
        self.path = args.path
        self.name = os.path.basename(os.path.dirname(os.path.join(self.path, ".")))
        if args.json:
            with open(args.zip_file, "r", encoding='utf-8') as f:
                self.campaign = json.load(f, object_pairs_hook=OrderedDict)
            self.campaign["jukeboxfolder"] = ""
        else:
            self.zip = zipfile.ZipFile(args.zip_file, "r")
            self.campaign = json.load(self.getZipFile("campaign.json"), object_pairs_hook=OrderedDict)
        self.packs = {}
        self.system_manifest = None
        self.system_templates = {}
        self.game_system = self.getArgument("game_system", foundry.DEFAULT_GAME_SYSTEM)
        self.game_system_version = foundry.DEFAULT_SYSTEM_VERSION
        if (self.game_system == ""):
            self.game_system = foundry.DEFAULT_GAME_SYSTEM
        self.fvtt_path = self.getArgument("fvtt_data_path", None)
        if self.fvtt_path is not None:
            # Accept an installation directory as well as the data directory:
            # a portable install keeps Config/options.json beside the app and
            # its data elsewhere, and the install folder is what a user knows.
            resolved = utils.resolveFVTTDataPath(self.fvtt_path)
            if resolved is None:
                self.logWarning(
                    "Warning: '%s' does not contain Data/systems and names no usable "
                    "dataPath in Config/options.json. Compendium enrichment will be "
                    "skipped." % self.fvtt_path)
            elif resolved != self.fvtt_path:
                self.logInfo("Using FVTT data path '%s' from '%s'."
                             % (resolved, self.fvtt_path))
            self.fvtt_path = resolved
        if self.fvtt_path is None:
            potential_path = os.path.abspath(os.path.join(self.path, "..", "..", ".."))
            if os.path.exists(os.path.join(potential_path, "Data", "systems", self.game_system, "system.json")):
                self.fvtt_path = potential_path
            else:
                self.fvtt_path = utils.getFVTTDataPath()
                if not utils.isFVTTDataPath(self.fvtt_path):
                    self.logWarning(
                        "Warning: no Foundry data directory found (looked at '%s'). "
                        "Pass --fvtt-data-path with your Foundry data or installation "
                        "directory, or set FOUNDRY_VTT_DATA_PATH."
                        % self.fvtt_path)
                    self.fvtt_path = None
        self.loadSystemManifest()
        if self.game_system == "dnd5e":
            if self.fvtt_path is not None:
                self.loadDnD5ePacks()
            else:
                self.logWarning("Warning: Could not find the path to the FVTT Data directory, either specify a destination directory in the Data/worlds/ path\n"
                  "or use the --fvtt-data-path argument to specify the path to the Data directory.\n"
                  "If you do not, then Item and Spell Compendium links in journal entries will not be replaced with links to SRD data from the D&D 5e packs.")
        else:
            try:
                loaded_templates = False
                if self.fvtt_path is not None:
                    self.loadSystemTemplate()
                    self.loadSystemPacks()
                    self.loadSystemVersion()
                    loaded_templates = True
            except Exception as e:
                self.logWarning(str(e))
                pass
            if not loaded_templates:
                self.logWarning("Warning: Could not find the path to the FVTT Data directory or the system you specified is not installed locally.\n"
                  "Your character sheets may fail to open.")

    def getZipFile(self, filename):
        # On japanese systems, path separator is actually '¥' which won't work
        # when opening the files in the zip.
        return self.zip.open(filename.replace(os.path.sep, "/"))

    def getArgument(self, name, default=None):
        return getattr(self.args, name, default)

    def loadSystemManifest(self):
        path = os.path.join(self.fvtt_path, "Data", "systems", self.game_system, "system.json")
        try:
            with open(path, "r", encoding='utf-8') as f:
                self.system_manifest = json.load(f)
                # Make sure the game system is capitalized properly.
                self.game_system = self.system_manifest.get("id", self.system_manifest.get("name", self.game_system))
        except:
            pass

    def warnIfLevelDBPacks(self, packs_dir):
        """Report the one cause behind a run of pack-load failures (B031).

        Systems have shipped LevelDB pack *directories* since Foundry v11. This
        converter reads the older newline-delimited JSON, so every pack fails
        with an unhelpful per-file error unless the real reason is named.
        """
        try:
            entries = os.listdir(packs_dir)
        except OSError:
            return False
        leveldb = [e for e in entries
                   if os.path.isdir(os.path.join(packs_dir, e))
                   and os.path.exists(os.path.join(packs_dir, e, "CURRENT"))]
        if not leveldb:
            return False
        self.logWarning(
            "Warning: '%s' contains LevelDB pack directories (%s), which this version cannot read.\n"
            "Compendium enrichment is disabled for this conversion: items, spells and class features\n"
            "will not be matched against the game system's content, so they keep the Roll20 icons and\n"
            "descriptions and compendium links in journals are left as Roll20 URLs.\n"
            "The conversion itself is unaffected."
            % (packs_dir, ", ".join(sorted(leveldb)[:5])))
        return True

    def loadDnD5ePacks(self):
        self.packs = {}
        packs_dir = os.path.join(self.fvtt_path, "Data", "systems", "dnd5e", "packs")
        if self.warnIfLevelDBPacks(packs_dir):
            return
        for file in ["items", "spells", "classfeatures", "classes", "monsters"]:
            db  = DatabaseFile(self, "%s.db" % file, "dnd5e", file)
            path = os.path.join(packs_dir, "%s.db" % file)
            try:
                db.load(path)
                self.packs[file] = db
            except Exception as e:
                self.logWarning("Warning: Could not load dnd5e compendium pack '%s.db': %s" % (file, e))

    def loadSystemPacks(self):
        self.packs = {}
        self.logInfo("Loading System Compendium Packs...")
        packs_dir = os.path.join(self.fvtt_path, "Data", "systems", self.game_system, "packs")
        if self.warnIfLevelDBPacks(packs_dir):
            return
        for pack in self.system_manifest.get('packs', []):
            db  = DatabaseFile(self, "%s.db" % pack['name'], self.game_system, pack['name'])
            path = os.path.join(self.fvtt_path, "Data", "systems", self.game_system, pack['path'])
            try:
                db.load(path)
                self.packs[pack['name']] = db
            except Exception as e:
                self.logWarning("Warning: Could not load compendium pack '%s' (%s.db): %s" % (pack['name'], pack['name'], e))
    def loadSystemVersion(self):
        path = os.path.join(self.fvtt_path, "Data", "systems", self.game_system, "system.json")
        with open(path, "r", encoding='utf-8') as f:
            module = json.load(f)
        self.game_system_version = module.get("version", self.game_system_version)
        # Ensure the system matches case sensitivity of the name
        self.game_system = module.get("name", self.game_system)

    def mergeDictionaries(self, destination, source):
        """Recursively merge ``source`` into ``destination`` and return it.

        Values in ``source`` win over values already in ``destination``; nested
        dictionaries are merged rather than replaced wholesale. Used to flatten
        a game system's ``template.json`` inheritance ("templates" lists) into a
        single concrete actor template.

        >>> converter = R20Converter.__new__(R20Converter)
        >>> a = {'first': {'all_rows': {'pass': 'dog', 'number': '1'}}}
        >>> b = {'first': {'all_rows': {'fail': 'cat', 'number': '5'}}}
        >>> converter.mergeDictionaries(b, a) == {'first': {'all_rows': {'pass': 'dog', 'fail': 'cat', 'number': '1'}}}
        True
        """
        for key, value in source.items():
            if isinstance(value, dict):
                # get node or create one
                node = destination.setdefault(key, {})
                self.mergeDictionaries(node, value)
            else:
                destination[key] = value

        return destination

    def loadSystemTemplate(self):
        path = os.path.join(self.fvtt_path, "Data", "systems", self.game_system, "template.json")
        with open(path, "r", encoding='utf-8') as f:
            template = json.load(f)
        self.system_templates = {}
        for actor_type in template["Actor"]["types"]:
            actor_template = template["Actor"][actor_type]
            actor_templates = actor_template.get("templates", [])
            if "templates" in actor_template:
                del actor_template["templates"]
            for sub_template in actor_templates:
                self.mergeDictionaries(actor_template, template["Actor"]["templates"].get(sub_template, {}))
            self.system_templates[actor_type] = actor_template
    def hasSystemPacks(self):
        return len(self.packs) > 0

    def convert(self):
        self.logInfo("*** Converting Campaign '%s' ***" % self.campaign["campaign_title"])
        os.makedirs(self.path)
        Actors.setRelease(self.campaign.get("release", "legacy"))
        Scenes.setRelease(self.campaign.get("release", "legacy"))
        if self.getArgument("export_as_module", False):
            os.makedirs(os.path.join(self.path, "packs"))

            # actors and journals can modify the items list, so create the correct class
            # and overwrite it with an emptyDB later if needed
            self.items = Items(self)

            if self.getArgument("disable_module_journal", False):
                self.journal = EmptyDB(self, "journal")
            else:
                self.journal = Journal(self)

            if self.getArgument("disable_module_actors", False):
                self.actors = EmptyDB(self, "actors")
            else:
                self.actors = Actors(self)

            if self.game_system != "dnd5e" or self.getArgument("disable_module_items", False):
                self.items = EmptyDB(self, "items")
            else:
                self.items.createEntities()

            if self.getArgument("disable_module_scenes", False):
                self.scenes = EmptyDB(self, "scenes")
            else:
                self.scenes = Scenes(self)

            if self.getArgument("disable_module_playlists", False):
                self.playlists = EmptyDB(self, "playlists")
            else:
                self.playlists = Playlists(self)

            if self.getArgument("disable_module_tables", False):
                self.tables = EmptyDB(self, "tables")
            else:
                self.tables = RollableTables(self)
            if self.getArgument("disable_module_decks", False):
                self.cards = EmptyDB(self, "cards")
                self.decks = EmptyDB(self, "decks")
            else:
                self.cards = Items(self, "cards.db")
                self.decks = Decks(self)

            if self.getArgument("disable_module_items", False):
                self.items = EmptyDB(self, "items")

            # Module will add the packs that are not empty and save them to file
            self.module = Module(self).save()
        else:
            os.makedirs(os.path.join(self.path, "data"))
            os.makedirs(os.path.join(self.path, "scenes", "thumbs"))

            self.settings = SettingsDB(self).save()
            self.users = Users(self).save()
            self.folders = Folders(self)
            self.macros = Macros(self).save()
            if self.getArgument("dont_convert_chat", False):
                self.chat = EmptyDB(self, "chat").save()
            else:
                self.chat = ChatLog(self).save()
            # Items DB needs to happen as two separate calls due to cross links
            self.items = Items(self)
            self.items.createEntities()
            self.journal = Journal(self).save()
            self.actors = Actors(self).save()
            self.scenes = Scenes(self).save()
            self.combat = Combat(self).save()
            self.playlists = Playlists(self).save()
            # Use items database for deck cards
            self.cards = self.items
            self.tables = Tables(self).save()

            self.sessions = EmptyDB(self, "sessions").save()
            # Could get modified by the journal or rollable tables
            self.folders.save()
            self.items.save()
            self.world = World(self).save()

    def logInfo(self, msg):
        self._logger.logInfo(msg)
    def logWarning(self, msg):
        self._logger.logWarning(msg)
    def logError(self, msg):
        self._logger.logError(msg)

if __name__ == "__main__":
    print("Please use main.py to run R20Converter")