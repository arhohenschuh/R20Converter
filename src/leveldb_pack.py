"""Foundry LevelDB compendium pack writing (ADR-009).

Since Foundry v11 a compendium pack is a LevelDB directory rather than a NeDB
``.db`` file. The layout was read out of a published module that runs on 14.365
rather than guessed:

- primary documents are keyed ``!<collection>!<id>``
- embedded documents are keyed ``!<collection>.<embedded>!<parentId>.<childId>``
- values are plain UTF-8 JSON, uncompressed
- the primary document keeps each embedded collection as an **array of ids**

Embedding is recursive. An effect on an actor item is stored under
``!actors.items.effects!<actor>.<item>.<effect>`` and a Token ActorDelta under
``!scenes.tokens.delta!<scene>.<token>.<delta>``. Array-valued relationships
leave arrays of ids in their parents; singleton relationships leave one id.

``plyvel`` is optional: the frozen build bundles it, and a source install
without it falls back to NeDB (see :func:`isAvailable`).
"""

import json
import os
import shutil

try:
    import plyvel
    IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - exercised by the fallback path
    # Not just ImportError: a native extension can fail on a missing DLL, and
    # a fallback that will not say why is the silent degradation F031 removed.
    plyvel = None
    IMPORT_ERROR = "%s: %s" % (type(exc).__name__, exc)


#: Pack file name (without ``.db``) to the Foundry collection its documents
#: belong to. Two packs hold a document type that does not match their name:
#: ``decks`` holds RollTables and ``cards`` holds Items. Mirrors the packs
#: ``module.py`` registers; ``test_leveldb_pack.py`` asserts they stay in step.
PACK_COLLECTIONS = {
    "adventure": "adventures",
    "journal": "journal",
    "actors": "actors",
    "items": "items",
    "scenes": "scenes",
    "playlists": "playlists",
    "tables": "tables",
    "decks": "tables",
    "cards": "items",
}

#: Embedded fields Foundry stores as separate entries. Values are ``many`` for
#: id arrays or ``one`` for a singleton id. Paths are explicit so ordinary
#: nested dictionaries carrying ``_id`` values are never mistaken for
#: documents.
EMBEDDED_COLLECTIONS = {
    "actors": {"items": "many", "effects": "many"},
    "actors.items": {"effects": "many"},
    "items": {"effects": "many"},
    "journal": {"pages": "many"},
    "tables": {"results": "many"},
    "playlists": {"sounds": "many"},
    "cards": {"cards": "many"},
    "scenes": {
        "drawings": "many", "lights": "many", "notes": "many",
        "sounds": "many", "templates": "many", "tiles": "many",
        "tokens": "many", "walls": "many",
    },
    "scenes.tokens": {"delta": "one"},
    "scenes.tokens.delta": {"items": "many", "effects": "many"},
    "scenes.tokens.delta.items": {"effects": "many"},
}


#: Key prefixes in a pack that are not documents. Foundry stores a pack's
#: folder tree under ``!folders!``, and those entries carry a ``name`` -- a
#: folder called "Wand" would answer a lookup for the item of that name.
NON_DOCUMENT_COLLECTIONS = ("folders",)

#: Folder ``type`` each pack's tree uses (ADR-010). Compendium folders are
#: scoped to the pack holding them, so a pack carries only its own type --
#: a JournalEntry folder in the actors pack would be an unreachable orphan.
PACK_FOLDER_TYPES = {
    "journal": "JournalEntry",
    "actors": "Actor",
    "items": "Item",
    "scenes": "Scene",
    "playlists": "Playlist",
    "tables": "RollTable",
    "decks": "RollTable",
    "cards": "Item",
}


def isAvailable():
    """Whether LevelDB packs can be written at all."""
    return plyvel is not None


def collectionFor(pack_name):
    """Collection name for a pack, or ``None`` if it is not one we map."""
    return PACK_COLLECTIONS.get(pack_name)


def folderTypeFor(pack_name):
    """Folder ``type`` a pack's tree must use, or ``None`` if unmapped."""
    return PACK_FOLDER_TYPES.get(pack_name)


def _key(collection, document_id):
    return ("!%s!%s" % (collection, document_id)).encode("utf-8")


def _value(document):
    return json.dumps(document).encode("utf-8")


def _documentId(document, collection, parent_ids, singleton=False):
    document_id = document.get("_id")
    if document_id is None and singleton and parent_ids:
        document_id = parent_ids[-1]
        document["_id"] = document_id
    if not document_id:
        raise ValueError("%s embedded document has no _id" % collection)
    return document_id


def _splitDocument(document, collection, parent_ids, singleton=False):
    primary = dict(document)
    document_id = _documentId(primary, collection, parent_ids, singleton)
    document_ids = parent_ids + (document_id,)
    children = []

    for field, cardinality in EMBEDDED_COLLECTIONS.get(collection, {}).items():
        value = primary.get(field)
        child_collection = "%s.%s" % (collection, field)
        if cardinality == "one":
            if value is None:
                continue
            if not isinstance(value, dict):
                raise ValueError("%s must contain a document or null" % child_collection)
            child, descendants = _splitDocument(
                value, child_collection, document_ids, singleton=True)
            child_id = child["_id"]
            primary[field] = child_id
            children.append((child_collection,
                             ".".join(document_ids + (child_id,)), child))
            children.extend(descendants)
            continue

        if value is None:
            continue
        if not isinstance(value, list):
            raise ValueError("%s must contain an array" % child_collection)
        ids = []
        seen = set()
        for entry in value:
            if not isinstance(entry, dict):
                raise ValueError("%s contains an id without its document" % child_collection)
            child, descendants = _splitDocument(entry, child_collection, document_ids)
            child_id = child["_id"]
            if child_id in seen:
                raise ValueError("%s contains duplicate id %s" %
                                 (child_collection, child_id))
            seen.add(child_id)
            ids.append(child_id)
            children.append((child_collection,
                             ".".join(document_ids + (child_id,)), child))
            children.extend(descendants)
        primary[field] = ids
    return primary, children


def splitDocument(document, collection):
    """Split one document into its primary form plus its embedded entries.

    Returns ``(primary, [(key_suffix, child), ...])``. The primary is a copy
    whose embedded collections have been replaced by id arrays, so the caller's
    document is left untouched.
    """
    if not isinstance(document, dict):
        raise ValueError("%s primary document is not an object" % collection)
    return _splitDocument(document, collection, ())


def writePack(path, documents, collection, folders=()):
    """Write ``documents`` to the LevelDB pack at ``path``.

    An existing pack is removed first: LevelDB would otherwise merge the new
    documents into the old ones, leaving anything renamed or deleted behind as
    an orphan that Foundry still shows.

    ``folders`` are written under ``!folders!`` so the pack keeps the Roll20
    hierarchy rather than importing flat (ADR-010).
    """
    if plyvel is None:
        raise RuntimeError("plyvel is not available")

    records = []
    keys = set()
    for folder in folders:
        if not folder.get("_id"):
            raise ValueError("folder document has no _id")
        record = (_key("folders", folder.get("_id")), _value(folder))
        if record[0] in keys:
            raise ValueError("duplicate LevelDB key %s" % record[0].decode("utf-8"))
        keys.add(record[0])
        records.append(record)
    for document in documents:
        primary, children = splitDocument(document, collection)
        for child_collection, child_key, child in children:
            record = (_key(child_collection, child_key), _value(child))
            if record[0] in keys:
                raise ValueError("duplicate LevelDB key %s" % record[0].decode("utf-8"))
            keys.add(record[0])
            records.append(record)
        record = (_key(collection, primary.get("_id")), _value(primary))
        if record[0] in keys:
            raise ValueError("duplicate LevelDB key %s" % record[0].decode("utf-8"))
        keys.add(record[0])
        records.append(record)

    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.exists(path):
        os.remove(path)
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)

    db = plyvel.DB(path, create_if_missing=True)
    try:
        with db.write_batch() as batch:
            for key, value in records:
                batch.put(key, value)
    finally:
        db.close()
    return path


def readPack(path, collection=None, strict=True):
    """Read a pack back, folding embedded entries into their parents.

    ``collection`` is optional: a primary document is one whose key prefix has
    no dot, which is how a system pack can be read without knowing in advance
    what it holds -- dnd5e ships packs named ``spells24`` and ``actors24`` whose
    names say nothing about their document type.

    Also what replaces ``type actors.db`` when a conversion needs debugging,
    since ADR-009 gives up greppable JSON for module packs.
    """
    if plyvel is None:
        raise RuntimeError("plyvel is not available")
    primaries = {}
    documents_by_path = {}
    collections_by_path = {}
    children_by_parent = {}
    db = plyvel.DB(path, create_if_missing=False)
    try:
        for raw_key, raw_value in db:
            key = raw_key.decode("utf-8")
            try:
                _, prefix, identifier = key.split("!", 2)
            except ValueError:
                continue
            document = json.loads(raw_value.decode("utf-8"))
            if "." in prefix:
                documents_by_path[identifier] = document
                collections_by_path[identifier] = prefix
                parent_path, child_id = identifier.rsplit(".", 1)
                field = prefix.rsplit(".", 1)[1]
                children_by_parent.setdefault((parent_path, field), {})[child_id] = document
            elif prefix in NON_DOCUMENT_COLLECTIONS:
                continue
            elif collection is None or prefix == collection:
                primaries[identifier] = document
                documents_by_path[identifier] = document
                collections_by_path[identifier] = prefix
    finally:
        db.close()

    problems = []
    for parent_path, field in children_by_parent:
        if parent_path not in documents_by_path:
            problems.append("%s.%s has no parent document" % (parent_path, field))
    for parent_path in sorted(documents_by_path,
                              key=lambda value: len(value.split(".")), reverse=True):
        parent = documents_by_path[parent_path]
        parent_collection = collections_by_path[parent_path]
        for field, cardinality in EMBEDDED_COLLECTIONS.get(parent_collection, {}).items():
            declared = parent.get(field)
            children = children_by_parent.get((parent_path, field), {})

            if cardinality == "one":
                if declared is None:
                    if children:
                        problems.append("%s.%s has orphan singleton children" %
                                        (parent_path, field))
                        if not strict and len(children) == 1:
                            parent[field] = next(iter(children.values()))
                    continue
                if not isinstance(declared, str):
                    problems.append("%s.%s is inline instead of a singleton id" %
                                    (parent_path, field))
                    continue
                child = children.get(declared)
                if child is None:
                    problems.append("%s.%s references missing id %s" %
                                    (parent_path, field, declared))
                    continue
                if len(children) != 1:
                    problems.append("%s.%s references one of %d children" %
                                    (parent_path, field, len(children)))
                parent[field] = child
                continue

            if declared is None:
                declared = []
            if not isinstance(declared, list) or any(not isinstance(item, str)
                                                     for item in declared):
                problems.append("%s.%s is inline instead of an id array" %
                                (parent_path, field))
                continue
            missing = [child_id for child_id in declared if child_id not in children]
            orphaned = [child_id for child_id in children if child_id not in declared]
            if missing:
                problems.append("%s.%s references missing ids %s" %
                                (parent_path, field, ", ".join(missing)))
            if orphaned:
                problems.append("%s.%s has orphan ids %s" %
                                (parent_path, field, ", ".join(orphaned)))
            if not missing and not orphaned:
                parent[field] = [children[child_id] for child_id in declared]
            elif not strict:
                ordered = [children[child_id] for child_id in declared
                           if child_id in children]
                ordered.extend(children[child_id] for child_id in sorted(orphaned))
                parent[field] = ordered

    if strict and problems:
        raise ValueError("invalid embedded LevelDB relationships: %s" % "; ".join(problems))
    return list(primaries.values())
