import os
import base64
import json
import re
import shutil
import urllib
import errno
import hashlib
import requests
import uuid
import copy
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import leveldb_pack

# --- Asset download tuning -------------------------------------------------
# A campaign can reference thousands of remote assets. Without a timeout a
# single stalled connection hangs the whole conversion, and without retries a
# momentary blip loses an image permanently.
#: (connect, read) timeout in seconds for every asset request.
DOWNLOAD_TIMEOUT = (10, 60)
#: How many times to retry a connection error or a retryable server response.
DOWNLOAD_RETRIES = 3
#: Exponential backoff factor between retries (0.5 -> 0.5s, 1s, 2s).
DOWNLOAD_BACKOFF = 0.5

# Roll20's image proxy returns this fixed body with HTTP 200 for dead images.
# A non-empty response is not evidence that art exists (B080).
ROLL20_PLACEHOLDER_BYTES = 10750
ROLL20_PLACEHOLDER_SHA1 = "f5c88ae6ead6d209ddf0fdd2a21a755aa6688f5a"


class Roll20PlaceholderError(ValueError):
    """A source returned Roll20's known dead-image placeholder."""


def isRoll20Placeholder(content):
    return (len(content or b"") == ROLL20_PLACEHOLDER_BYTES
            and hashlib.sha1(content).hexdigest() == ROLL20_PLACEHOLDER_SHA1)

_session = None


def _resourceSession():
    """Return the process-wide :class:`requests.Session` used for assets.

    A single session lets us reuse HTTP connections across the thousands of
    requests a large campaign makes, and gives one place to configure retries.
    Only transient failures are retried: 404 is a real answer ("this resolution
    does not exist") and is handled by the caller's resolution fallback.
    """
    global _session
    if _session is None:
        session = requests.Session()
        retry = Retry(total=DOWNLOAD_RETRIES, connect=DOWNLOAD_RETRIES,
                      read=DOWNLOAD_RETRIES, status=DOWNLOAD_RETRIES,
                      backoff_factor=DOWNLOAD_BACKOFF,
                      status_forcelist=(429, 500, 502, 503, 504),
                      allowed_methods=frozenset(["GET"]),
                      raise_on_status=False)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        _session = session
    return _session

class DatabaseFile(object):
    def __init__(self, converter, filename, package=None, pack_name=None):
        self._converter = converter
        self._path = converter.path
        self._filename = filename
        self._campaign = converter.campaign
        # Save package and pack name
        self._package = package
        self._pack_name = pack_name
        # If exporting to module, then init package/pack name from converter
        if package is None and self.getArgument("export_as_module", False):
            self._package = converter.name
            # Anchored: an unescaped ".db" is a regex matching any character,
            # so "adb.db" collapsed to "".
            self._pack_name = re.sub(r"\.db$", "", filename)
        self.entities = []
  
    def logInfo(self, msg):
        self._converter.logInfo(msg)
    def logWarning(self, msg):
        self._converter.logWarning(msg)
    def logError(self, msg):
        self._converter.logError(msg)

    def findID(self, id, where=None):
        if where == "handout" or where is None:
            matches = [item for item in self._campaign["handouts"] if item["id"] == id]
            if len(matches) > 0:
                return matches[0]
        if where == "page" or where is None:
            matches = [item for item in self._campaign["pages"] if item["id"] == id]
            if len(matches) > 0:
                return matches[0]
        if where == "character" or where is None:
            matches = [item for item in self._campaign["characters"] if item["id"] == id]
            if len(matches) > 0:
                return matches[0]
        if where == "player" or where is None:
            matches = [item for item in self._campaign["players"] if item["id"] == id]
            if len(matches) > 0:
                return matches[0]
        if where == "track" or where is None:
            matches = [item for item in self._campaign["jukebox"] if item["id"] == id]
            if len(matches) > 0:
                return matches[0]
        # Roll20 allows PDFs in the journal tree. Looked up last so no existing
        # unqualified findID() result changes; only ids that used to resolve to
        # nothing can now resolve to a PDF (B053).
        if where == "pdf" or where is None:
            matches = [item for item in self._campaign.get("pdfs", []) if item["id"] == id]
            if len(matches) > 0:
                return matches[0]
        return None

    def getBy(self, field, value, respect_case=True):
        value = value if respect_case else value.lower()
        for entity in self.entities:
            if field in entity.entity:
                ent_value = entity.entity[field] if respect_case else entity.entity[field].lower()
                if value == ent_value:
                    return entity
        return None

    def getById(self, id, respect_case=True):
        return self.getBy("_id", id, respect_case)
    def getByName(self, name, respect_case=True):
        return self.getBy("name", name, respect_case)

    def findCompendiumItem(self, compendium, item_name):
        converter = self._converter
        if converter.hasSystemPacks():
            db = None
            if compendium == "Spells":
                db = converter.packs.get("spells", None)
            elif compendium == "Items":
                db = converter.packs.get("items", None)
            elif compendium == "Classes":
                db = converter.packs.get("classes", None)
            elif compendium == "Class Features":
                db = converter.packs.get("classfeatures", None)
            if db:
                item = db.getByName(item_name, False)
                if item is None and item_name.lower() == "enlarge reduce":
                    # 'Enlarge/Reduce' is 'Enlarge Reduce' in Roll20's compendium
                    return db.getByName("Enlarge/Reduce", False)
                return item
        return None

    def findCompendiumActor(self, actor_name):
        converter = self._converter
        if converter.system_manifest is not None and converter.hasSystemPacks():
            packs = converter.system_manifest.get("packs", [])
            for pack in packs:
                entityType = pack.get('entity', None) or pack.get('type', None)
                if entityType != "Actor":
                    continue
                db = converter.packs.get(pack['name'], None)
                if db is None:
                    continue
                actor = db.getByName(actor_name, False)
                if actor:
                    return actor
        return None
            
    def getArgument(self, name, default=None):
        return self._converter.getArgument(name, default)

    def __str__(self):
        return "\n".join(map(str, self.entities))

    def getDirectoryName(self):
        if self.getArgument("export_as_module", False):
            return "packs"
        else:
            return "data"

    def _levelDBCollection(self):
        """Collection to write as a LevelDB pack, or ``None`` for NeDB.

        Worlds keep NeDB deliberately (ADR-009): Foundry's world migration is
        automatic and measured lossless, so only module packs are worth the
        native dependency.
        """
        if not self.getArgument("export_as_module", False):
            return None
        name = re.sub(r"\.db$", "", self._filename)
        collection = leveldb_pack.collectionFor(name)
        if collection is None:
            return None
        if not leveldb_pack.isAvailable():
            self.logWarning(
                "LevelDB support is unavailable (%s), writing '%s' as a NeDB "
                "file. Foundry will convert it on import; install plyvel to "
                "have the pack written directly."
                % (leveldb_pack.IMPORT_ERROR, name))
            return None
        return collection

    def _packFolders(self):
        """Folder documents for this pack, scoped to its own type (ADR-010).

        A world writes ``folders.db`` instead, and a pack we do not map has no
        tree to carry, so both return nothing.
        """
        folders = getattr(self._converter, "folders", None)
        if folders is None or folders is self:
            return []
        folder_type = leveldb_pack.folderTypeFor(re.sub(r"\.db$", "", self._filename))
        if folder_type is None:
            return []
        return folders.forType(folder_type)

    def save(self, full_path=None):
        collection = self._levelDBCollection()
        if collection is not None:
            if full_path is None:
                full_path = os.path.join(self._path, self.getDirectoryName(),
                                         re.sub(r"\.db$", "", self._filename))
            leveldb_pack.writePack(full_path,
                                   [entity.entity for entity in self.entities],
                                   collection,
                                   folders=self._packFolders())
            return self
        if full_path is None:
            full_path = os.path.join(self._path, self.getDirectoryName(), self._filename)
        with open(full_path, "w", encoding='utf-8') as f:
            f.write(str(self))
        return self

    def load(self, full_path=None):
        if full_path is None:
            full_path = os.path.join(self._path, self.getDirectoryName(), self._filename)
        self.entities = []
        if os.path.isdir(full_path):
            if not leveldb_pack.isAvailable():
                raise IOError("'%s' is a LevelDB pack and LevelDB support is "
                              "unavailable (%s)" % (full_path, leveldb_pack.IMPORT_ERROR))
            name = os.path.basename(full_path.rstrip("\\/"))
            # A system pack is named for its content, not its document type, so
            # the collection is read off the keys rather than assumed.
            collection = leveldb_pack.collectionFor(name)
            for data in leveldb_pack.readPack(
                    full_path, collection, strict=self._package is None):
                self.entities.append(Entity.createFromData(self, data))
            return
        with open(full_path, "r", encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines:
                self.entities.append(Entity.createFromData(self, json.loads(line)))


class Entity(object):
    # Foundry's CONST.DOCUMENT_OWNERSHIP_LEVELS. The numeric values are
    # unchanged since v9; only the document field they are written to was
    # renamed from `permission` to `ownership` in v10 (ADR-002).
    OWNERSHIP_NONE = 0
    # -1 means "inherit from the parent document" (Foundry's INHERIT level).
    OWNERSHIP_INHERIT = -1
    OWNERSHIP_LIMITED = 1
    OWNERSHIP_OBSERVER = 2
    OWNERSHIP_OWNER = 3
    # Foundry's ShapeData.TYPES. The v9 text ("t") and freehand ("f") drawing
    # types no longer exist: text is a rectangle carrying text, and freehand is
    # a polygon with a non-zero bezierFactor (ADR-002).
    SHAPE_RECTANGLE = "r"
    SHAPE_CIRCLE = "c"
    SHAPE_ELLIPSE = "e"
    SHAPE_POLYGON = "p"
    SORT_ORDER = 10000
    # Ensures ids are unique accross all entities
    id_database = {}
    uuids = []
    #: Maps a source URL to the path of the file we already wrote for it, so a
    #: URL referenced by many entities is fetched once. Deliberately stores
    #: *paths* rather than response bodies: caching bytes made this dict grow to
    #: the full size of the campaign's media, which exhausts memory on
    #: map-heavy campaigns.
    resource_cache = {}

    def __init__(self, database, id):
        self._database = database
        self._converter = database._converter
        self._original_id = id if id else self.genID()
        self._id = self.normalizeID(self._original_id)
        self.entity = {"_id": self._id}

    def documentStats(self):
        """The ``_stats`` block every document should carry (ADR-008).

        R20Converter emitted none at all, which leaves ``_stats.systemVersion``
        unset. dnd5e reads that field to decide whether a document needs
        migrating, so an absent value invites a migration over documents that
        are already current — and that migration is what empties
        ``system.damage.base``.
        """
        import dnd5e
        import foundry
        converter = getattr(self, "_converter", None)
        version = getattr(converter, "game_system_version", None) \
            or foundry.DEFAULT_SYSTEM_VERSION
        return dnd5e.stats(foundry.DOCUMENT_SCHEMA_CORE_VERSION, version)

    def logInfo(self, msg):
        self._database.logInfo(msg)
    def logWarning(self, msg):
        self._database.logWarning(msg)
    def logError(self, msg):
        self._database.logError(msg)

    @staticmethod
    def createFromData(database, data):
        entity = Entity(database, data["_id"])
        entity._id = entity._original_id
        entity.entity = data
        return entity

    def getID(self, normalized=True):
        return self._id if normalized else self._original_id

    def findID(self, id, where=None):
        return self._database.findID(id, where)

    @property
    def isCompendiumEntity(self):
        return self._database._package is not None

    def getFullID(self):
        if not self.isCompendiumEntity:
            return self.getID()
        return "%s.%s.%s" % (self._database._package, self._database._pack_name, self.getID())

    @staticmethod
    def shape(width, height, shape_type=None, points=None):
        """Build a Foundry ShapeData object for a Drawing.

        Foundry v10 moved the drawing's `type`, `width`, `height` and `points`
        into this nested object and the migration was removed in 12.316
        (ADR-002). Points are a flat `[x0, y0, x1, y1, ...]` number array, not
        a list of pairs.
        """
        return {
            "type": shape_type or Entity.SHAPE_RECTANGLE,
            "width": width,
            "height": height,
            "points": points or [],
        }

    @staticmethod
    def texture(src, tint=None, scale_x=1, scale_y=1, anchor=0, fit="fill", alpha_threshold=0):
        """Build a Foundry TextureData object.

        Foundry v10 replaced the flat `img`/`tint`/`scale`/`mirrorX`/`mirrorY`
        fields on scenes, tiles and tokens with this shared structure, and the
        migration was removed in 12.316 (ADR-002). Mirroring is expressed as a
        negative scale rather than a separate flag.
        """
        return {
            "src": src or None,
            "anchorX": anchor,
            "anchorY": anchor,
            "offsetX": 0,
            "offsetY": 0,
            "fit": fit,
            "scaleX": scale_x,
            "scaleY": scale_y,
            "rotation": 0,
            "tint": tint or "#ffffff",
            "alphaThreshold": alpha_threshold,
        }

    @staticmethod
    def compendiumUuid(full_id, document):
        """Turn a "<packageId>.<packName>.<id>" key into a Foundry v13 UUID.

        Foundry v11 added the document type as an explicit segment, so a
        compendium UUID reads
        "Compendium.<packageId>.<packName>.<DocumentName>.<id>".
        """
        (package, pack, id) = full_id.rsplit(".", 2)
        return "Compendium.%s.%s.%s.%s" % (package, pack, document, id)

    def addToOwnedList(self, parent_list):
        entity = copy.deepcopy(self.entity)
        entity["_id"] = self.genID()
        entity["sort"] = (len(parent_list) + 1) * Entity.SORT_ORDER
        parent_list.append(entity)
        return entity

    def findCompendiumItem(self, compendium, item_name):
        item = self._database.findCompendiumItem(compendium, item_name)
        return Entity.normalizeSystemData(item)

    def findCompendiumActor(self, actor_name):
        actor = self._database.findCompendiumActor(actor_name)
        return Entity.normalizeSystemData(actor)

    @staticmethod
    def normalizeSystemData(entity):
        """Ensure a compendium document uses the v10+ ``system`` key.

        Documents read out of an installed game system's compendium packs may
        predate the v10 rename of ``Document#data`` to ``Document#system``.
        Foundry removed the automatic migration in 12.316 (ADR-002), so we
        normalise on read and speak the v13 vocabulary everywhere downstream.

        Accepts and returns ``None`` so callers can pass a lookup result
        straight through.
        """
        if entity is not None and "data" in entity.entity and "system" not in entity.entity:
            entity.entity["system"] = entity.entity.pop("data")
        return entity

    def getArgument(self, name, default=None):
        return self._database.getArgument(name, default)

    def replaceEntityLinks(self, content):
        content = self.replaceMarkdownLinks(content)
        return re.sub('<a ([^>]*)href=[\'"]http://journal.roll20.net/([^/]+)/([^\'"]+)[\'"]([^>]*)>(.*?)</a>', self._foundJournal, content)

    @staticmethod
    def replaceMarkdownLinks(content):
        def replace(match):
            label, target = match.groups()
            target = target.replace("&", "&amp;").replace('"', "&quot;")
            return '<a href="%s">%s</a>' % (target, label)
        return re.sub(r'(?<!!)\[([^\]\n]+)\]\(([^)\n]+)\)', replace, content)

    def replaceCompendiumLinks(self, content):
        return re.sub('<a ([^>]*)href=[\'"]https?://roll20.net/compendium/dnd5e/([^\'"]+)(?:(?:%3[aA])|:)([^\'"]+)[\'"]([^>]*)>(.*?)</a>', self._foundCompendium, content)

    def _foundCompendium(self, match):
        converter = self._converter
        before_href = match.group(1)
        compendium = match.group(2)
        name = urllib.parse.unquote(match.group(3))
        name = name.split("#")[0].split("?")[0]
        after_href = match.group(4)
        text = match.group(5)
        item = converter.items.getByName(name)
        if item is None:
            if compendium == "Spells":
                folder = "D&D 5e Spells (SRD)"
                folder_id = "r20converter-dnd5e-spells"
            elif compendium == "Items":
                folder = "D&D 5e Items (SRD)"
                folder_id = "r20converter-dnd5e-items"
            else:
                folder = "Compendium"
                folder_id = "r20converter-dnd5e-compendium"
            compendium_item = self.findCompendiumItem(compendium, name)
            if self.getArgument("export_as_module", False):
                if compendium_item:
                    return "@UUID[%s]{%s}" % (
                        Entity.compendiumUuid(compendium_item.getFullID(), "Item"), name)
                self.logWarning("Could not find compendium item of type '%s' and name '%s'"
                                % (compendium, name))
                return text
            elif compendium_item:
                converter.folders.ensureFolder(folder_id, folder, "Item")
                item = converter.items.createItemFromCompendium(None, compendium_item)
                item.entity["folder"] = Entity.normalizeID(folder_id)
                converter.items.addEntity(item)
        if item:
            return self.replaceEntityLinks('<a %shref="http://journal.roll20.net/item/%s"%s>%s</a>' % (before_href, item.getID(), after_href, text))
        else:
            self.logWarning("Could not find compendium item of type '%s' and name '%s'" % (compendium, name))
            return match.group(0)
        

    def _foundJournal(self, match):
        before_href = match.group(1)
        journal = match.group(2)
        id = match.group(3)
        after_href = match.group(4)
        text = match.group(5)
        if journal in ["handout", "character", "item"]:
            target = None
            if journal == "item":
                converter = getattr(self, "_converter", None)
                items = getattr(converter, "items", None)
                if items is not None:
                    target = items.getById(Entity.normalizeID(id))
            if target is None:
                target = self.findID(id, journal)
            if target is None:
                self.logWarning("Roll20 %s link '%s' targets a document absent from the export"
                                % (journal, text))
                return text
            #icon = {"handout": "fa-book-open", "character": "fa-user", "item": "fa-suitcase"}[journal]
            #return '<a class="entity-link" data-entity=%s data-id=%s %s%s><i class="fas %s"></i>%s</a>' % (entity, self.normalizeID(id), before_href, after_href, icon, text)
            label = re.sub("[<>}{]", "_", text)
            document = {"handout": "JournalEntry", "character": "Actor", "item": "Item"}[journal]
            if self.isCompendiumEntity:
                pack = {"handout": "journal", "character": "actors", "item": "items"}[journal]
                target = Entity.compendiumUuid(
                    "%s.%s.%s" % (self._database._package, pack, self.normalizeID(id)), document)
            else:
                target = "%s.%s" % (document, self.normalizeID(id))
            return '@UUID[%s]{%s}' % (target, label)
        else:
            return match.group(0)

    @staticmethod
    def textToHtml(text):
        if type(text) == list:
            text_list = text
        else:
            text_list = text.split("\n")
        # Replace each line with <p>line</p>
        try:
            return "".join(list(map(lambda l: "<p>" + l + "</p>", text_list)))
        except:
            # Ignore description in the case of a non list of strings, which can happen apparently.
            return ""

    @staticmethod
    def strToID(id_str):
        new_str = hashlib.sha256(id_str.encode()).hexdigest()
        return base64.b64encode(new_str[-12:].encode()).decode()
    
    @staticmethod
    def hashString(str):
        return hashlib.sha256(str.encode()).hexdigest()


    @staticmethod
    def normalizeID(id):
        if id is None or id == "":
            return None
        if id in Entity.id_database:
            return Entity.id_database[id]
        normalized_id = Entity.strToID(id)
        index = 0
        while normalized_id in Entity.id_database.values():
            #self.logInfo("Found an ID conflict for %s=%s\n%s" % (id, normalized_id, str(Entity.id_database)))
            new_id = "%s%d" % (id, index)
            normalized_id = Entity.strToID(new_id)
            index += 1
        Entity.id_database[id] = normalized_id
        return normalized_id

    @staticmethod
    def genID():
        id = uuid.uuid4()
        while id in Entity.uuids:
            id = uuid.uuid4()
        Entity.uuids.append(id)
        return Entity.normalizeID(str(id))

    # Used to fix the sometimes broken color codes in R20
    @staticmethod
    def color(val, default="#c0c0c0", allow_transparent=False):
        if not isinstance(val, str):
            return default
        val = val.strip().lower()
        if allow_transparent and val == "transparent":
            return None
        m = re.fullmatch(
            r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)"
            r"(?:\s*,\s*(?:0|1|0?\.\d+))?\s*\)", val)
        if m:
            rgb = tuple(map(int, m.groups()))
            if all(0 <= channel <= 255 for channel in rgb):
                return "#%02x%02x%02x" % rgb
            return default
        if not val.startswith("#") or len(val) < 4:
            return default
        val = val[1:]
        try:
            if len(val) < 6:
                # CSS shorthand repeats each nibble: #abc is #aabbcc, so 0xa -> 0xaa.
                # Indices 0-2 also drop the alpha nibble of the #rgba form.
                rgb = tuple(int(val[i], 16) * 17 for i in (0, 1, 2))
            else:
                rgb = tuple(int(val[i:i+2], 16) for i in (0, 2, 4))
            return "#%02x%02x%02x" % rgb
        except:
            return default

    @staticmethod
    def urlsafe(filename):
        url = urllib.parse.quote(filename.replace(os.path.sep, "/").replace(" ", "_"))
        # Url encoded characters won't resolve, since the URL would become invalid, so we replace them
        urlsafe = re.sub("%([0-9A-F]{2})", "_\\1", url)
        urlsafe = re.sub(r"\.+/", "_/", urlsafe)
        return urlsafe

    def getDirectoryName(self):
        world_dir_name = os.path.basename(os.path.dirname(os.path.join(self._database._path, ".")))
        if self.getArgument("export_as_module", False):
            directory = "modules"
        else:
            directory = "worlds"
        return os.path.join(directory, world_dir_name)

    def getDestinationPaths(self, destination, url=None, type=None, dedup=None):
        # Remove leading, trailing and duplicate spaces in the destination name
        destination = re.sub(" +", " ", destination).strip()
        if dedup is None:
            dedup = self.getArgument("dedup_assets", False)
        if dedup is True and url is not None:
            splitext = os.path.splitext(destination)
            filename = self.hashString(url) + splitext[1]
            dir = self.getArgument("assets_directory", "assets")
            if type is not None:
                dir = os.path.join(dir, type)
            destination = os.path.join(dir, filename)
            destination_safe = self.urlsafe(destination)
            dest_filename = os.path.join(self._database._path, destination_safe).replace(os.path.sep, "/")
        else:
            index = 1
            destination_safe = self.urlsafe(destination)
            while True:
                dest_filename = os.path.join(self._database._path, destination_safe).replace(os.path.sep, "/")
                # Check for conflicts
                if os.path.exists(dest_filename):
                    splitext = os.path.splitext(destination)
                    new_destination = "%s_%d%s" % (splitext[0], index, splitext[1])
                    destination_safe = self.urlsafe(new_destination)
                    index += 1
                else:
                    break

        # Check if the destination path we found is longer than the max path and replace it with an assets directory instead
        max_path = self.getArgument("max_path", 256)
        abspath = os.path.abspath(os.path.join(self._database._path, destination_safe))
        if len(abspath) >= max_path:
            base = os.path.basename(destination)
            new_destination = os.path.join(self.getArgument("assets_directory", "assets"), base)
            #print("destination", destination, "is too long (", len(abspath), " > ", max_path,"), trying with assets directory instead")
            #print("Base ", base, " - new destination ", new_destination)
            # Try with 'assets/${basename}" first, then try with incremental numbers if that's still too long.
            if new_destination != destination:
                return self.getDestinationPaths(new_destination, url, type, dedup)
            else:
                # We already tried 'assets/$basename' and it's still too long, let's try numbers now, but don't check for length anymore
                index = 1
                splitext = os.path.splitext(destination)
                new_destination = os.path.join(self.getArgument("assets_directory", "assets"), "%d%s" % (index, splitext[1]))
                destination_safe = self.urlsafe(new_destination)
                while True:
                    dest_filename = os.path.join(self._database._path, destination_safe).replace(os.path.sep, "/")
                    # Check for conflicts
                    if os.path.exists(dest_filename):
                        index += 1
                        new_destination = os.path.join(self.getArgument("assets_directory", "assets"), "%d%s" % (index, splitext[1]))
                        destination_safe = self.urlsafe(new_destination)
                    else:
                        break

        # Defence in depth: destination names are derived from untrusted campaign
        # JSON and ZIP entry names. urlsafe() neutralises "../" sequences, but a
        # future change there must never be able to make us write outside the
        # world/module directory, so assert containment before creating anything.
        self._assertWithinOutputDirectory(dest_filename)

        try:
            os.makedirs(os.path.dirname(dest_filename))
        except OSError as e:
            if e.errno == errno.EEXIST:
                pass
            else:
                raise

        config_path = os.path.join(self.getDirectoryName(), destination_safe)
        return (dest_filename, config_path.replace(os.path.sep, "/"))

    def _assertWithinOutputDirectory(self, dest_filename):
        """Raise if ``dest_filename`` resolves outside the output directory."""
        root = os.path.abspath(self._database._path)
        resolved = os.path.abspath(dest_filename)
        if resolved != root and not resolved.startswith(root + os.path.sep):
            raise ValueError("Refusing to write asset outside of the output directory: %s" % dest_filename)
    
    def fixImageUrl(self, url):
        if url == "":
            return ""
        if not url.startswith("http"):
            url = "https://app.roll20.net/" + url
        # all Roll20 URLs use thumb/med/max/original for the filename but the actual image
        # loaded depends on the size. If we don't grab the original image, then maps will be
        # of much lower resolution than they should be.
        # Also remove the '?number' at the end of URLs because they seem unnecessary and they
        # break FVTT which doesn't recognize the URL as having a valid extension.
        url = re.sub(r"/(thumb|med|max)\.([^/]*)$", r"/original.\2", url)
        return url

    # Foundry refuses to render a path whose extension is not one of these
    # (CONST.IMAGE_FILE_EXTENSIONS / VIDEO_FILE_EXTENSIONS / AUDIO_FILE_EXTENSIONS).
    RENDERABLE_EXTENSIONS = frozenset([
        "apng", "avif", "bmp", "gif", "jpeg", "jpg", "png", "svg", "tiff", "webp",
        "m4v", "mp4", "ogv", "webm",
        "aac", "flac", "m4a", "mid", "mp3", "ogg", "opus", "wav", "webm",
    ])
    # Aliases Roll20 serves that hold a format Foundry does render.
    EXTENSION_ALIASES = {"jfif": "jpg", "jpe": "jpg", "jif": "jpg", "jfi": "jpg", "tif": "tiff"}

    def assetExtension(self, url):
        """Return the file extension to store a Roll20 asset under, or "".

        Roll20 URLs carry cache-busting fragments after either `?` or `&`, and the
        extension they advertise is not always one Foundry can render -- a `.jfif`
        map is dropped silently by the client (B056). Keep only the leading
        alphanumeric run and translate known aliases.
        """
        match = re.match(r"\.[A-Za-z0-9]+", os.path.splitext(url)[1])
        if not match:
            return ""
        extension = match.group(0)
        suffix = extension[1:].lower()
        if suffix in self.EXTENSION_ALIASES:
            return "." + self.EXTENSION_ALIASES[suffix]
        return extension

    def downloadResource(self, url, destination, type=None, dedup=None):
        extension = self.assetExtension(url)
        if extension:
            splitext = os.path.splitext(destination)
            destination = splitext[0] + extension
        (dest_filename, config_path) = self.getDestinationPaths(destination, url, type, dedup)
        # getDestinationPaths should always return a unique new file, unless dedup is enabled
        # So if the file already exists, assume dedup is enabled and return the file directly
        # without downloading (or copy from cache)
        if os.path.exists(dest_filename):
            return (dest_filename, config_path)
        originalUrl = url

        # Cache hit: the same URL was already downloaded for another entity, so
        # copy the file we wrote then rather than fetching it again. The cache
        # deliberately stores paths, not bytes -- see the resource_cache comment
        # on Entity.
        cached = Entity.resource_cache.get(originalUrl, None)
        if cached is not None and os.path.exists(cached):
            shutil.copyfile(cached, dest_filename)
            return (dest_filename, config_path)

        content = self._fetchResource(self.fixImageUrl(url), originalUrl)
        if content is None:
            self.logWarning("Failed to download URL : %s" % originalUrl)
            return (None, "")

        with open(dest_filename, "wb") as f:
            f.write(content)
        Entity.resource_cache[originalUrl] = dest_filename
        return (dest_filename, config_path)

    @staticmethod
    def hostCandidates(url):
        """Return ``url`` spelled for every Roll20 CDN host, best first.

        Roll20 moved its asset CDN: objects that used to be served from
        ``s3.amazonaws.com/files.d20.io/...`` now answer on ``files.d20.io/...``
        directly, and the old spelling returns 403 for everything (B048). The
        bucket name is the first path segment, so the new URL is recoverable
        from the old one without a lookup. The renamed host goes first because
        it is the one that currently answers; the original is kept as a fallback
        so nothing regresses if Roll20 moves back.
        """
        parsed = urlparse(url)
        if parsed.netloc != "s3.amazonaws.com":
            return [url]
        segments = parsed.path.lstrip("/").split("/", 1)
        if len(segments) != 2 or segments[0] not in ("files.d20.io", "files.staging.d20.io"):
            return [url]
        renamed = parsed._replace(netloc=segments[0], path="/" + segments[1]).geturl()
        return [renamed, url]

    def _fetchResource(self, url, originalUrl):
        """Fetch ``url``, degrading through Roll20's image resolutions.

        Roll20 serves each image under ``original``/``max``/``med``/``thumb``
        names, but not every image exists at every resolution. ``fixImageUrl``
        optimistically rewrites the URL to ``original``; if that 404s we walk
        down to progressively smaller variants rather than losing the asset.
        The walk only applies when ``fixImageUrl`` actually rewrote the URL --
        for a non-Roll20 URL there is nothing to degrade to.

        Each resolution is tried on every known CDN host before dropping to a
        smaller one, so a host rename never costs image quality (B048).

        Returns the response body, or ``None`` if every attempt failed. All
        failures are logged with their cause: a silent failure here used to be
        indistinguishable from a legitimately missing image.
        """
        candidates = [url]
        if url != originalUrl:
            for pattern, replacement in ((r"/original\.([^/]*)$", r"/max.\1"),
                                         (r"/max\.([^/]*)$", r"/med.\1"),
                                         (r"/med\.([^/]*)$", r"/thumb.\1")):
                nextUrl = re.sub(pattern, replacement, candidates[-1])
                if nextUrl == candidates[-1]:
                    break
                candidates.append(nextUrl)

        placeholder_seen = False
        for candidate in candidates:
            for spelling in Entity.hostCandidates(candidate):
                try:
                    # A timeout is mandatory here: without one a stalled connection
                    # blocks the entire conversion indefinitely. Connection errors
                    # and 5xx responses are retried with backoff by the session
                    # adapter; a 404 is not retried, we fall through to the next
                    # resolution instead.
                    response = _resourceSession().get(spelling, timeout=DOWNLOAD_TIMEOUT)
                except requests.RequestException as e:
                    self.logWarning("Error downloading '%s': %s" % (spelling, e))
                    continue
                if response.status_code == 200:
                    if response.content:
                        if isRoll20Placeholder(response.content):
                            placeholder_seen = True
                            self.logWarning(
                                "Rejected Roll20 dead-image placeholder from '%s'" % spelling)
                            continue
                        return response.content
                    self.logWarning("Error downloading '%s': HTTP 200 with empty body"
                                    % spelling)
                    continue
                self.logWarning("Error downloading '%s': HTTP %d" % (spelling, response.status_code))
        if placeholder_seen:
            raise Roll20PlaceholderError(
                "Roll20 placeholder returned for every usable candidate: %s" % originalUrl)
        return None

    @staticmethod
    def getImageFilename(base_path, url, base_filename, fallback=".png"):
        filename = urlparse(url).path
        ext = os.path.splitext(filename)[1]
        if not ext:
            ext = fallback
        return os.path.join(base_path, base_filename + ext)
    
    def copyZipFile(self, url, filename, destination, type=None, dedup=None):
        zipfile = None
        # Two different extensions, and conflating them is B056. R20Exporter names the
        # zip member from the raw URL (its ADR-003), so the lookup must keep `.jfif` and
        # any `&cb=` fragment; the file we write to disk must not, or Foundry will not
        # draw it.
        zip_extension = None
        if url:
            zip_extension = os.path.splitext(url)[1].split("?")[0]
        dest_extension = self.assetExtension(url) if url else ""
        if dest_extension:
            splitext = os.path.splitext(destination)
            destination = splitext[0] + dest_extension
        (dest_filename, config_path) = self.getDestinationPaths(destination, url, type, dedup)
        # getDestinationPaths should always return a unique new file, unless dedup is enabled
        # So if the file already exists, assume dedup is enabled and return the file directly
        # without copying it from the zip a second time
        if os.path.exists(dest_filename):
            return (dest_filename, config_path)
        # R20Exporter 0.14.0+ records the path it actually wrote for every asset. Trust
        # that over our own derivation, which cannot know about entity types we do not
        # consume -- a single PDF in a journal folder shifted 111 paths by one (B053).
        manifest_path = self._database._converter.getZipPathForUrl(url)
        if manifest_path:
            try:
                zipfile = self._database._converter.getZipFile(manifest_path)
            except Exception:
                zipfile = None
        try:
            if zipfile is None:
                zipfile = self._database._converter.getZipFile(filename)
        except Exception as e:
            if zip_extension:
                splitext = os.path.splitext(filename)
                if zip_extension != splitext[1]:
                    filename = splitext[0] + zip_extension
                    try:
                        zipfile = self._database._converter.getZipFile(filename)
                    except:
                        pass

        if zipfile is None:
            self._database._converter.noteZipMiss(filename)
            # B049: the export zip is not the only copy. The asset URL is still in
            # hand, so a miss here is a reason to download, not to give up -- the
            # old behaviour dropped the image and left the document pointing at
            # nothing. Only give up once the download has failed too.
            if url:
                self.logWarning("Cannot find file '%s' in Zip, downloading instead" % filename)
                return self.downloadResource(url, destination, type, dedup)
            self.logWarning("Cannot find file '%s' in Zip" % filename)
            return (None, "")
        content = zipfile.read()
        if not content:
            self.logWarning("File '%s' in Zip is empty, downloading instead" % filename)
            if url:
                return self.downloadResource(url, destination, type, dedup)
            return (None, "")
        if isRoll20Placeholder(content):
            self.logWarning("Rejected Roll20 dead-image placeholder in Zip file '%s'" % filename)
            if url:
                return self.downloadResource(url, destination, type, dedup)
            raise Roll20PlaceholderError(
                "Roll20 placeholder in Zip file without a fallback URL: %s" % filename)
        with open(dest_filename, "wb") as f:
            f.write(content)
        return (dest_filename, config_path)

    def __str__(self):
        if self.getArgument("export_as_module", False):
            return json.dumps(self.entity)
        return json.dumps(self.nedbSafeData(self.entity))

    @staticmethod
    def nedbSafeData(value, location="$"):
        """Return a NeDB-serializable copy with safe object field names.

        NeDB rejects every literal ``.`` and leading ``$`` in an object key.
        Compendium provenance flags can legitimately carry version labels such
        as ``beyond5e-2.5.0``; copying those labels into a world makes Foundry's
        one-time NeDB-to-LevelDB migration abort before the world launches.
        Module packs stay byte-faithful because LevelDB does not use this path.
        """
        if isinstance(value, list):
            return [Entity.nedbSafeData(item, "%s[%d]" % (location, index))
                    for index, item in enumerate(value)]
        if not isinstance(value, dict):
            return value
        normalized = {}
        sources = {}
        for key, item in value.items():
            safe_key = str(key).replace(".", "_")
            if safe_key.startswith("$"):
                safe_key = "_" + safe_key[1:]
            if safe_key in normalized and sources[safe_key] != key:
                raise ValueError(
                    "NeDB key collision at %s: %r and %r normalize to %r"
                    % (location, sources[safe_key], key, safe_key))
            sources[safe_key] = key
            child = "%s.%s" % (location, safe_key)
            normalized[safe_key] = Entity.nedbSafeData(item, child)
        return normalized

class EmptyDB(DatabaseFile):
    def __init__(self, converter, name):
        DatabaseFile.__init__(self, converter, name + ".db")