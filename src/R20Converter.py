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
import leveldb_pack
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
    LOG_FILENAME = "conversion-log.txt"

    def __init__(self, args, logger=None):
        self._logger = utils if logger is None else logger
        self._log_fh = None
        self._log_disabled = False
        self._log_buffer = []
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
        self.zip_paths_by_url = {}
        self.export_report = None
        self._zip_misses = 0
        if not args.json:
            self.loadExportReport()
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

    def loadExportReport(self):
        """Map asset URL -> the path the exporter actually wrote (R20Exporter 0.14.0+).

        Re-deriving that path from campaign.json is what B053 got wrong: the exporter
        numbers every sibling in a journal folder, we skipped the types we do not
        consume, and every later path was off by one. Read the path when it is given.

        Most of the export archive predates this file, so it is an improvement on the
        derivation and not a replacement for fixing it.
        """
        try:
            with self.getZipFile("export_report.json") as f:
                report = json.load(f)
        except Exception:
            return
        for asset in report.get("assets") or []:
            url = asset.get("url")
            path = asset.get("path")
            if url and path and asset.get("outcome") not in ("failed", "skipped"):
                self.zip_paths_by_url.setdefault(url, path)
        if not self.zip_paths_by_url:
            return
        self.export_report = report
        self.logInfo("Export manifest found (R20Exporter %s): resolving %d asset paths by URL."
                     % (report.get("exporter_version", "?"), len(self.zip_paths_by_url)))

    def getZipPathForUrl(self, url):
        return self.zip_paths_by_url.get(url) if url else None

    def noteZipMiss(self, filename):
        """A single miss is plausible; a hundred means the paths are derived wrong."""
        self._zip_misses += 1
        if self._zip_misses == 25 and not self.zip_paths_by_url:
            self.logWarning(
                "25+ assets were not found at their derived zip paths. That pattern is a "
                "path-derivation fault far more often than an incomplete export (B053) — "
                "re-exporting with R20Exporter 0.14.0 or later lets the converter read the "
                "paths from the export manifest instead of recomputing them.")

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
        """Report unreadable LevelDB packs (B031).

        Systems have shipped LevelDB pack *directories* since Foundry v11.
        Since ADR-009 those are readable, so this only fires when LevelDB
        support is missing -- a source install without plyvel -- and names the
        one cause rather than letting every pack fail separately.
        """
        if leveldb_pack.isAvailable():
            return False
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
            "Warning: '%s' contains LevelDB pack directories (%s), which this build cannot\n"
            "read: %s.\n"
            "Compendium enrichment is disabled for this conversion: items, spells and class features\n"
            "will not be matched against the game system's content, so they keep the Roll20 icons and\n"
            "descriptions and compendium links in journals are left as Roll20 URLs.\n"
            "The conversion itself is unaffected."
            % (packs_dir, ", ".join(sorted(leveldb)[:5]), leveldb_pack.IMPORT_ERROR))
        return True

    def _packPath(self, packs_dir, name, declared=None):
        """Locate a pack, preferring the LevelDB directory over a NeDB file."""
        candidates = []
        if declared:
            candidates.append(os.path.join(self.fvtt_path, "Data", "systems",
                                           self.game_system, declared))
        candidates.append(os.path.join(packs_dir, name))
        candidates.append(os.path.join(packs_dir, "%s.db" % name))
        for candidate in candidates:
            if os.path.isdir(candidate) or os.path.isfile(candidate):
                return candidate
        return None

    def loadDnD5ePacks(self):
        self.packs = {}
        packs_dir = os.path.join(self.fvtt_path, "Data", "systems", "dnd5e", "packs")
        if self.warnIfLevelDBPacks(packs_dir):
            return
        edition = self.getArgument("srd_edition", None) or foundry.DEFAULT_SRD_EDITION
        mapping = foundry.DND5E_SRD_PACKS.get(edition)
        if mapping is None:
            self.logWarning("Warning: unknown SRD edition '%s', using %s."
                            % (edition, foundry.DEFAULT_SRD_EDITION))
            edition = foundry.DEFAULT_SRD_EDITION
            mapping = foundry.DND5E_SRD_PACKS[edition]

        loaded = 0
        cache = {}
        for role, pack in mapping.items():
            path = self._packPath(packs_dir, pack)
            if path is None:
                continue
            if pack not in cache:
                # 2024 keeps classes and their features in one pack; read it once.
                db = DatabaseFile(self, "%s.db" % pack, "dnd5e", pack)
                try:
                    db.load(path)
                except Exception as e:
                    self.logWarning("Warning: Could not load dnd5e compendium pack '%s': %s"
                                    % (pack, e))
                    continue
                cache[pack] = db
                loaded += len(db.entities)
            self.packs[role] = cache[pack]
        if self.packs:
            self.logInfo("Loaded %d documents from %d dnd5e %s SRD compendium packs (%s)."
                         % (loaded, len(cache), edition, ", ".join(sorted(cache))))
        self.loadCustomCompendium()

    def resolveCustomCompendium(self, name):
        """Locate a custom compendium's ``packs`` directory.

        ``name`` is a module id or a path. The id is preferred because it is
        portable between machines and the data directory is already known; a
        path is accepted for a module kept outside it.
        """
        candidates = []
        if self.fvtt_path:
            candidates.append(os.path.join(self.fvtt_path, "Data", "modules", name))
        candidates.append(name)
        for candidate in candidates:
            if not os.path.isdir(candidate):
                continue
            packs = os.path.join(candidate, "packs")
            if os.path.isdir(packs):
                return packs
            if os.path.isdir(os.path.join(candidate, "CURRENT")):
                continue
            # Pointed straight at a packs directory.
            if any(os.path.isdir(os.path.join(candidate, e, "")) for e in os.listdir(candidate)):
                return candidate
        return None

    def loadCustomCompendium(self):
        """Merge a user-supplied compendium module into the system packs."""
        name = self.getArgument("custom_compendium", None)
        if not name:
            return
        packs_dir = self.resolveCustomCompendium(name)
        if packs_dir is None:
            self.logWarning(
                "Warning: custom compendium '%s' was not found as a module id under "
                "Data/modules or as a path, so it is ignored." % name)
            return

        buckets = {}
        total = 0
        for entry in sorted(os.listdir(packs_dir)):
            path = os.path.join(packs_dir, entry)
            if not os.path.isdir(path):
                continue
            db = DatabaseFile(self, "%s.db" % entry, name, entry)
            try:
                db.load(path)
            except Exception as e:
                self.logWarning("Warning: Could not load custom compendium pack '%s': %s"
                                % (entry, e))
                continue
            for entity in db.entities:
                role = foundry.COMPENDIUM_DOCUMENT_ROLES.get(entity.entity.get("type"))
                if role:
                    buckets.setdefault(role, []).append(entity)
                    total += 1
        if not buckets:
            self.logWarning("Warning: custom compendium '%s' held no documents this "
                            "converter can use." % name)
            return

        mode = self.getArgument("custom_compendium_mode", None) or foundry.DEFAULT_CUSTOM_MODE
        precedence = (self.getArgument("custom_compendium_precedence", None)
                      or foundry.DEFAULT_CUSTOM_PRECEDENCE)
        for role, entities in buckets.items():
            merged = DatabaseFile(self, "%s.db" % role, name, role)
            existing = self.packs.get(role)
            if mode == "replace" or existing is None:
                merged.entities = list(entities)
            elif precedence == "custom":
                # getBy returns the first match, so order *is* the precedence.
                merged.entities = list(entities) + list(existing.entities)
            else:
                merged.entities = list(existing.entities) + list(entities)
            self.packs[role] = merged
        self.logInfo("Loaded %d documents from custom compendium '%s' (%s, %s precedence): %s."
                     % (total, name, mode, precedence, ", ".join(sorted(buckets))))
        self.warnAboutCompendiumAssets(name, buckets)

    def warnAboutCompendiumAssets(self, name, buckets):
        """Name the modules a custom compendium's artwork lives in.

        Matched documents keep their own ``img``, and a compendium module often
        stores artwork in a *separate* assets module. Anything converted with it
        then needs that module installed too, which is otherwise discovered as
        missing images long after the conversion.
        """
        modules = set()
        for entities in buckets.values():
            for entity in entities:
                image = entity.entity.get("img") or ""
                parts = image.replace("\\", "/").split("/")
                if len(parts) > 2 and parts[0] == "modules":
                    modules.add(parts[1])
        modules.discard(name)
        if modules:
            self.logWarning(
                "Note: artwork from '%s' lives in %s. Anything matched against it keeps "
                "those image paths, so %s must also be installed wherever this conversion "
                "is opened."
                % (name, ", ".join("'%s'" % m for m in sorted(modules)),
                   "that module" if len(modules) == 1 else "those modules"))

    def loadSystemPacks(self):
        self.packs = {}
        self.logInfo("Loading System Compendium Packs...")
        packs_dir = os.path.join(self.fvtt_path, "Data", "systems", self.game_system, "packs")
        if self.warnIfLevelDBPacks(packs_dir):
            return
        for pack in self.system_manifest.get('packs', []):
            path = self._packPath(packs_dir, pack['name'], pack.get('path'))
            if path is None:
                continue
            db = DatabaseFile(self, "%s.db" % pack['name'], self.game_system, pack['name'])
            try:
                db.load(path)
                self.packs[pack['name']] = db
            except Exception as e:
                self.logWarning("Warning: Could not load compendium pack '%s': %s" % (pack['name'], e))
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

    def _writeLog(self, msg):
        """Mirror a log line into the output folder so the run leaves a record.

        Buffered until ``convert()`` creates the output directory. Creating it
        here instead would pre-empt the bare ``os.makedirs`` in ``convert()``,
        which is the only thing stopping the GUI from converting into an
        existing world -- the CLI checks separately, the GUI does not.

        Every failure disables the file rather than aborting the conversion --
        a log is worth less than the run it describes.
        """
        if self._log_disabled:
            return
        try:
            if self._log_fh is None:
                if not os.path.isdir(self.path):
                    self._log_buffer.append(msg)
                    return
                self._log_fh = open(os.path.join(self.path, self.LOG_FILENAME),
                                    "w", encoding="utf-8")
                for buffered in self._log_buffer:
                    self._log_fh.write("%s\n" % buffered)
                self._log_buffer = []
            self._log_fh.write("%s\n" % msg)
            self._log_fh.flush()   # a crashed run must still leave its log behind
        except Exception:
            self._log_disabled = True
            self._log_fh = None
            self._log_buffer = []

    def closeLog(self):
        if self._log_fh is not None:
            try:
                self._log_fh.close()
            except Exception:
                pass
            self._log_fh = None

    def finishLog(self, message=None):
        """Append the closing message main.py prints, then release the file."""
        if message:
            self._writeLog(message)
        self.closeLog()

    def logInfo(self, msg):
        self._writeLog(msg)
        self._logger.logInfo(msg)
    def logWarning(self, msg):
        self._writeLog(msg)
        self._logger.logWarning(msg)
    def logError(self, msg):
        self._writeLog(msg)
        self._logger.logError(msg)

if __name__ == "__main__":
    print("Please use main.py to run R20Converter")