"""Self-contained Foundry module assembly (v1.14.0)."""

import copy
import html
import json
import os
import re
import shutil

import dnd5e
import foundry
import leveldb_pack
from entities.base import (Entity, Roll20PlaceholderError,
                           isRoll20Placeholder)


COMPENDIUM_UUID_RE = re.compile(
    r"^Compendium\.([^.]+)\.([^.]+)\.(Actor|Item)\.([A-Za-z0-9]{16})$")
COMPENDIUM_UUID_INLINE_RE = re.compile(
    r"Compendium\.([^.\]\s]+)\.([^.\]\s]+)\.(Actor|Item)\.([A-Za-z0-9]{16})")
COMPENDIUM_PACKAGE_RE = re.compile(r"Compendium\.([^.\]\s]+)\.")
IMG_SRC_RE = re.compile(
    r"(<img\b[^>]*?\bsrc\s*=\s*)([\"'])(.*?)(\2)", re.IGNORECASE)
IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
ACTOR_TYPES = frozenset(("character", "npc", "vehicle", "group"))
EXECUTABLE_UUID_KEYS = frozenset(("uuid", "documentUuid", "targetUuid"))
PROVENANCE_UUID_KEYS = frozenset(("compendiumSource", "sourceId"))


class ModuleAssembler(object):
    """Close generic module dependencies and build one importable Adventure."""

    DATABASES = (
        ("journal", "journal"), ("actors", "actors"), ("items", "items"),
        ("scenes", "scenes"), ("playlists", "playlists"),
        ("tables", "tables"), ("decks", "decks"), ("cards", "cards"),
    )

    def __init__(self, converter):
        self.converter = converter
        self.recommendations = set()
        self._asset_helper = None
        self.placeholder_urls = set()
        self.placeholder_references = 0
        self.placeholder_tags_stripped = 0

    def _databases(self):
        for _, attribute in self.DATABASES:
            database = getattr(self.converter, attribute, None)
            if database is not None:
                yield database

    def _entities(self):
        seen = set()
        for database in self._databases():
            for entity in getattr(database, "entities", ()):
                if id(entity) in seen:
                    continue
                seen.add(id(entity))
                yield entity

    def _documents(self):
        for entity in self._entities():
            document = getattr(entity, "entity", None)
            if isinstance(document, dict):
                yield document

    @staticmethod
    def _walk(value):
        if isinstance(value, dict):
            for key, child in list(value.items()):
                yield value, key, child
                for result in ModuleAssembler._walk(child):
                    yield result
        elif isinstance(value, list):
            for index, child in enumerate(list(value)):
                yield value, index, child
                for result in ModuleAssembler._walk(child):
                    yield result

    @staticmethod
    def _walkWithItemImage(value, item_image=None):
        """Walk JSON values while carrying the nearest owning Item image."""
        if isinstance(value, dict):
            context_image = item_image
            if ("system" in value and "type" in value
                    and value.get("type") not in ACTOR_TYPES):
                context_image = value.get("img") or None
            for key, child in list(value.items()):
                yield value, key, child, context_image
                for result in ModuleAssembler._walkWithItemImage(child, context_image):
                    yield result
        elif isinstance(value, list):
            for index, child in enumerate(list(value)):
                yield value, index, child, item_image
                for result in ModuleAssembler._walkWithItemImage(child, item_image):
                    yield result

    @staticmethod
    def _documentType(document):
        return "Actor" if document.get("type") in ACTOR_TYPES else "Item"

    def _compendiumIndex(self):
        index = {}
        seen = set()
        for database in getattr(self.converter, "packs", {}).values():
            for entity in getattr(database, "entities", ()):
                if id(entity) in seen or not hasattr(entity, "getFullID"):
                    continue
                seen.add(id(entity))
                document = getattr(entity, "entity", {})
                document_type = self._documentType(document)
                try:
                    uuid = Entity.compendiumUuid(entity.getFullID(), document_type)
                except (AttributeError, TypeError, ValueError):
                    continue
                index[uuid] = entity
        return index

    def _localDatabase(self, document_type):
        return self.converter.actors if document_type == "Actor" else self.converter.items

    @staticmethod
    def _actorArtIsUsable(document):
        return bool(str(document.get("img") or "").strip()
                    and str(document.get("prototypeToken", {})
                            .get("texture", {}).get("src") or "").strip())

    def _cloneExecutableTarget(self, donor, document_type, fallback_image=None,
                               require_usable_art=False, source_uuid=None):
        target = self._localDatabase(document_type)
        source = copy.deepcopy(donor.entity)
        source["folder"] = None
        if document_type == "Actor":
            if require_usable_art and not self._actorArtIsUsable(source):
                fallback = (str(fallback_image or "").strip()
                            or str(source.get("img") or "").strip()
                            or str(source.get("prototypeToken", {})
                                   .get("texture", {}).get("src") or "").strip())
                if not fallback:
                    raise ValueError(
                        "Executable Actor %s has unusable art and no invoking Item icon"
                        % (source_uuid or source.get("_id")))
                source["img"] = source.get("img") or fallback
                token = source.setdefault("prototypeToken", {})
                token.setdefault("texture", {})["src"] = (
                    token.get("texture", {}).get("src") or fallback)
                if not self._actorArtIsUsable(source):
                    raise ValueError("Executable Actor %s still has unusable art" %
                                     (source_uuid or source.get("_id")))
            source.setdefault("prototypeToken", {})["displayName"] = 40
        identifier = source.get("_id")
        if not identifier:
            raise ValueError("executable compendium target has no document id")
        for existing in target.entities:
            if existing.entity.get("_id") != identifier:
                continue
            if existing.entity.get("name") != source.get("name"):
                raise ValueError("local executable id %s conflicts with '%s'" %
                                 (identifier, existing.entity.get("name")))
            return existing
        cloned = copy.copy(donor)
        cloned.entity = source
        cloned._database = target
        cloned._id = identifier
        cloned._original_id = identifier
        target.entities.append(cloned)
        if hasattr(cloned, "setPosition"):
            cloned.setPosition(len(target.entities))
        return cloned

    def localizeExecutableReferences(self):
        """Clone external Actor/Item UUID targets and rewrite them to local packs."""
        donors = self._compendiumIndex()
        while True:
            changed = False
            for document in list(self._documents()):
                for owner, key, value, item_image in self._walkWithItemImage(document):
                    if not isinstance(value, str) or key in PROVENANCE_UUID_KEYS:
                        continue
                    direct = COMPENDIUM_UUID_RE.match(value) if key in EXECUTABLE_UUID_KEYS else None
                    if key in EXECUTABLE_UUID_KEYS and direct is None:
                        if value.startswith("Compendium."):
                            raise ValueError("invalid executable compendium reference %s" % value)
                        continue

                    def replace(match):
                        nonlocal changed
                        package, _, document_type, identifier = match.groups()
                        if package == self.converter.name:
                            return match.group(0)
                        donor = donors.get(match.group(0))
                        if package == self.converter.game_system:
                            if document_type != "Actor":
                                return match.group(0)
                            if donor is None:
                                if direct is not None:
                                    raise ValueError(
                                        "unresolvable executable compendium reference %s" % value)
                                return match.group(0)
                            if self._actorArtIsUsable(donor.entity):
                                return match.group(0)
                            self._cloneExecutableTarget(
                                donor, document_type, fallback_image=item_image,
                                require_usable_art=True, source_uuid=match.group(0))
                            changed = True
                            return "Compendium.%s.actors.Actor.%s" % (
                                self.converter.name, identifier)
                        if donor is None:
                            if direct is not None:
                                raise ValueError(
                                    "unresolvable executable compendium reference %s" % value)
                            return match.group(0)
                        self._cloneExecutableTarget(donor, document_type)
                        changed = True
                        return "Compendium.%s.%s.%s.%s" % (
                            self.converter.name,
                            "actors" if document_type == "Actor" else "items",
                            document_type, identifier)

                    owner[key] = COMPENDIUM_UUID_INLINE_RE.sub(replace, value)
            if not changed:
                break
        self.validateExecutableReferences()

    def validateExecutableReferences(self):
        """Require every same-module executable UUID to resolve locally."""
        local = {
            ("Actor", "actors"): {
                entity.entity.get("_id") for entity in self.converter.actors.entities},
            ("Item", "items"): {
                entity.entity.get("_id") for entity in self.converter.items.entities},
            ("Item", "cards"): {
                entity.entity.get("_id") for entity in self.converter.cards.entities},
        }
        for document in self._documents():
            for _, key, value in self._walk(document):
                if key not in EXECUTABLE_UUID_KEYS or not isinstance(value, str):
                    continue
                match = COMPENDIUM_UUID_RE.match(value)
                if not match:
                    continue
                package, pack, document_type, identifier = match.groups()
                if package != self.converter.name:
                    continue
                if identifier not in local.get((document_type, pack), set()):
                    raise ValueError("local executable compendium reference does not resolve: %s"
                                     % value)

    def _assetHelper(self):
        if self._asset_helper is None:
            database = next(self._databases(), None)
            if database is None:
                raise ValueError("module has no database for asset ownership")
            helper = Entity.__new__(Entity)
            helper._database = database
            helper._converter = self.converter
            self._asset_helper = helper
        return self._asset_helper

    @staticmethod
    def _externalAsset(value):
        decoded = html.unescape(str(value or "")).strip()
        if decoded.startswith(("http://", "https://", "//", "/")):
            return decoded
        if decoded.startswith("modules/"):
            parts = decoded.replace("\\", "/").split("/")
            return decoded if len(parts) > 2 else ""
        return ""

    def _copyExternalAsset(self, value):
        source = self._externalAsset(value)
        if not source:
            return value
        helper = self._assetHelper()
        if source.startswith("//"):
            source = "https:" + source
        if source.startswith("modules/"):
            parts = source.replace("\\", "/").split("/")
            if parts[1] == self.converter.name:
                return source
            root = getattr(self.converter, "fvtt_path", None)
            path = os.path.join(root or "", "Data", "modules", *parts[1:])
            if not root or not os.path.isfile(path):
                return ""
            with open(path, "rb") as handle:
                content = handle.read()
            if isRoll20Placeholder(content):
                raise Roll20PlaceholderError(
                    "Roll20 placeholder in external module asset: %s" % source)
            destination = os.path.join("assets", "external", parts[-1])
            dest_filename, config_path = helper.getDestinationPaths(
                destination, source, type="external", dedup=True)
            if not os.path.exists(dest_filename):
                shutil.copyfile(path, dest_filename)
            return config_path

        manifest_path = self.converter.getZipPathForUrl(source) \
            if hasattr(self.converter, "getZipPathForUrl") else None
        destination = os.path.join("assets", "html", "embedded")
        _, config_path = helper.copyZipFile(
            source, manifest_path or "", destination, type="html", dedup=True)
        return config_path

    def _internalizeString(self, value):
        def replace_tag(tag_match):
            tag = tag_match.group(0)
            match = IMG_SRC_RE.search(tag)
            if not match:
                return tag
            source = match.group(3)
            external = self._externalAsset(source)
            if not external:
                return tag
            try:
                local = self._copyExternalAsset(external)
            except Roll20PlaceholderError:
                self.placeholder_urls.add(external)
                self.placeholder_references += 1
                self.placeholder_tags_stripped += 1
                return ""
            if not local:
                raise ValueError("could not internalize embedded image %s" % external)
            replacement = "%s%s%s%s" % (
                match.group(1), match.group(2), local, match.group(4))
            return tag[:match.start()] + replacement + tag[match.end():]

        updated = IMG_TAG_RE.sub(replace_tag, value) if "<img" in value.lower() else value
        external = self._externalAsset(updated)
        if external and re.search(r"\.[A-Za-z0-9]{2,5}(?:[?&].*)?$", external):
            local = self._copyExternalAsset(external)
            if not local:
                raise ValueError("could not internalize module asset %s" % external)
            return local
        return updated

    def internalizeAssets(self):
        """Move external document and HTML image references under this module."""
        for document in self._documents():
            for owner, key, value in self._walk(document):
                if isinstance(value, str):
                    owner[key] = self._internalizeString(value)
        if self.placeholder_tags_stripped and hasattr(self.converter, "logInfo"):
            self.converter.logInfo(
                "Roll20 placeholder art: %d URLs, %d references, %d stripped HTML tags, "
                "0 stored files" % (
                    len(self.placeholder_urls), self.placeholder_references,
                    self.placeholder_tags_stripped))

    def collectRecommendations(self):
        self.recommendations = set()
        for document in self._documents():
            for _, _, value in self._walk(document):
                if not isinstance(value, str):
                    continue
                for package in COMPENDIUM_PACKAGE_RE.findall(value):
                    if package not in (self.converter.name, self.converter.game_system):
                        self.recommendations.add(package)
        return self.recommendations

    def normalizeJournalHierarchy(self):
        """Project the source journalfolder tree onto pack and Adventure data."""
        documents = {entity.entity.get("_id"): entity
                     for entity in self.converter.journal.entities}
        handouts = {handout["id"]: handout
                    for handout in self.converter.campaign.get("handouts", [])}
        characters = {character["id"] for character
                      in self.converter.campaign.get("characters", [])}
        folders = []
        assignments = {}
        seen = set()

        def visit(nodes, parent=None, index_path=()):
            if not isinstance(nodes, list):
                raise ValueError("journalfolder %s children are not an array" %
                                 (".".join(map(str, index_path)) or "root"))
            descendants = 0
            for index, node in enumerate(nodes):
                path = index_path + (index,)
                if isinstance(node, str):
                    if node in seen:
                        raise ValueError("journalfolder source ref %s occurs more than once" % node)
                    seen.add(node)
                    if node in handouts:
                        document_id = Entity.normalizeID(node)
                        entity = documents.get(document_id)
                        if entity is None:
                            raise ValueError("source handout %s has no Journal document" % node)
                        assignments[document_id] = {
                            "folder": parent, "sort": (index + 1) * 100000}
                        descendants += 1
                    elif node not in characters:
                        continue
                    continue
                if (not isinstance(node, dict) or not str(node.get("n", "")).strip()
                        or not isinstance(node.get("i"), list)):
                    raise ValueError("malformed source Journal folder at %s" %
                                     ".".join(map(str, path)))
                seed = "source:%s" % ".".join(map(str, path))
                record = {
                    "_id": dnd5e.activityId("%s:folder:JournalEntry:%s" %
                                             (self.converter.name, seed)),
                    "name": node["n"], "type": "JournalEntry", "folder": None,
                    "sorting": "m", "sort": (index + 1) * 100000,
                    "flags": {self.converter.name: {
                        "sourceJournalFolder": True,
                        "sourceIndexPath": list(path)}},
                    "parent": parent, "descendants": 0,
                }
                folders.append(record)
                record["descendants"] = visit(node["i"], record, path)
                descendants += record["descendants"]
            return descendants

        visit(self.converter.campaign.get("journalfolder", []))
        included = [folder for folder in folders if folder["descendants"] > 0]
        included_ids = {folder["_id"] for folder in included}
        for folder in included:
            parent = folder.pop("parent")
            folder.pop("descendants")
            folder["folder"] = parent["_id"] if parent and parent["_id"] in included_ids else None
        for assignment in assignments.values():
            parent = assignment["folder"]
            assignment["folder"] = parent["_id"] if parent else None
        expected = {Entity.normalizeID(handout_id) for handout_id in handouts}
        if set(assignments) != expected or set(documents) != expected:
            raise ValueError("Journal source hierarchy does not cover every handout exactly once")
        for document_id, assignment in assignments.items():
            documents[document_id].entity["folder"] = assignment["folder"]
            documents[document_id].entity["sort"] = assignment["sort"]
        retained = [entity for entity in self.converter.folders.entities
                    if entity.entity.get("type") != "JournalEntry"]
        retained.extend(Entity.createFromData(self.converter.folders, folder)
                        for folder in included)
        self.converter.folders.entities = retained

    def _collection(self, attribute):
        database = getattr(self.converter, attribute, None)
        return [copy.deepcopy(entity.entity)
                for entity in getattr(database, "entities", ())
                if isinstance(getattr(entity, "entity", None), dict)]

    def buildAdventure(self):
        actors = self._collection("actors")
        scenes = self._collection("scenes")
        folders = self._collection("folders")
        actor_ids = {actor.get("_id") for actor in actors}
        folder_ids = {folder.get("_id") for folder in folders}
        if len(folder_ids) != len(folders):
            raise ValueError("Adventure contains duplicate folder ids")
        for folder in folders:
            if folder.get("folder") is not None and folder["folder"] not in folder_ids:
                raise ValueError("Adventure folder %s has a missing parent" % folder.get("_id"))
        for attribute in ("actors", "items", "scenes", "journal", "playlists",
                          "tables", "decks", "cards"):
            for document in self._collection(attribute):
                if document.get("folder") is not None and document["folder"] not in folder_ids:
                    raise ValueError("Adventure document %s has a missing folder" %
                                     document.get("_id"))
        for scene in scenes:
            for token in scene.get("tokens", []):
                if token.get("actorId") and token["actorId"] not in actor_ids:
                    raise ValueError("broken token actor link %s" % token["actorId"])

        title = self.converter.getArgument("campaign_title", None) \
            or self.converter.campaign["campaign_title"]
        version = self.converter.getArgument("package_version", None) or "1.0.0"
        cover = next((scene.get("thumb") for scene in scenes if scene.get("thumb")), None)
        if not cover:
            cover = next((actor.get("img") for actor in actors if actor.get("img")), None)
        return {
            "_id": dnd5e.activityId("%s:adventure" % self.converter.name),
            "name": "%s - Complete Adventure" % title,
            "img": cover or "icons/svg/book.svg",
            "caption": "One-click import of the module",
            "description": "<h1>%s <small>v%s</small></h1><p>Imports this module with stable document IDs.</p>" %
                           (title, version),
            "sort": 0,
            "actors": actors,
            "combats": [],
            "items": self._collection("items") + self._collection("cards"),
            "scenes": scenes,
            "journal": self._collection("journal"),
            "tables": self._collection("tables") + self._collection("decks"),
            "macros": [],
            "cards": [],
            "playlists": self._collection("playlists"),
            "folders": folders,
            "folder": None,
            "flags": {self.converter.name: {
                "builtBy": "R20Converter", "source": "Roll20 export"}},
            "_stats": dnd5e.stats(foundry.DOCUMENT_SCHEMA_CORE_VERSION,
                                   self.converter.game_system_version),
        }

    def writeAdventure(self, adventure):
        path = os.path.join(self.converter.path, "packs", "adventure")
        if leveldb_pack.isAvailable():
            leveldb_pack.writePack(path, [adventure], "adventures")
        else:
            with open(path + ".db", "w", encoding="utf-8") as handle:
                handle.write(json.dumps(adventure) + "\n")
        return path

    def prepare(self):
        self.normalizeJournalHierarchy()
        self.localizeExecutableReferences()
        self.internalizeAssets()
        self.collectRecommendations()
        return self.buildAdventure()