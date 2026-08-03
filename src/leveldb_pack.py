"""Foundry LevelDB compendium pack writing (ADR-009).

Since Foundry v11 a compendium pack is a LevelDB directory rather than a NeDB
``.db`` file. The layout was read out of a published module that runs on 14.365
rather than guessed:

- primary documents are keyed ``!<collection>!<id>``
- embedded documents are keyed ``!<collection>.<embedded>!<parentId>.<childId>``
- values are plain UTF-8 JSON, uncompressed
- the primary document keeps each embedded collection as an **array of ids**

Only the top level is split. An item inside an actor becomes its own
``!actors.items!`` entry, but that item's own ``effects`` stay inline, which is
what the reference module does.

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
    "journal": "journal",
    "actors": "actors",
    "items": "items",
    "scenes": "scenes",
    "playlists": "playlists",
    "tables": "tables",
    "decks": "tables",
    "cards": "items",
}

#: Collections Foundry stores as separate entries rather than inline.
EMBEDDED_COLLECTIONS = {
    "actors": ("items", "effects"),
    "items": ("effects",),
    "journal": ("pages",),
    "tables": ("results",),
    "playlists": ("sounds",),
    "cards": ("cards",),
    "scenes": ("drawings", "lights", "notes", "sounds", "templates", "tiles",
               "tokens", "walls"),
}


def isAvailable():
    """Whether LevelDB packs can be written at all."""
    return plyvel is not None


def collectionFor(pack_name):
    """Collection name for a pack, or ``None`` if it is not one we map."""
    return PACK_COLLECTIONS.get(pack_name)


def _key(collection, document_id):
    return ("!%s!%s" % (collection, document_id)).encode("utf-8")


def _value(document):
    return json.dumps(document).encode("utf-8")


def splitDocument(document, collection):
    """Split one document into its primary form plus its embedded entries.

    Returns ``(primary, [(key_suffix, child), ...])``. The primary is a copy
    whose embedded collections have been replaced by id arrays, so the caller's
    document is left untouched.
    """
    primary = dict(document)
    children = []
    parent_id = primary.get("_id")
    for field in EMBEDDED_COLLECTIONS.get(collection, ()):
        entries = primary.get(field)
        if not isinstance(entries, list) or not entries:
            continue
        ids = []
        for entry in entries:
            # Already an id array (a re-split, or a document we did not build).
            if not isinstance(entry, dict):
                ids.append(entry)
                continue
            child_id = entry.get("_id")
            if child_id is None:
                continue
            ids.append(child_id)
            children.append(("%s.%s" % (collection, field),
                             "%s.%s" % (parent_id, child_id), entry))
        primary[field] = ids
    return primary, children


def writePack(path, documents, collection):
    """Write ``documents`` to the LevelDB pack at ``path``.

    An existing pack is removed first: LevelDB would otherwise merge the new
    documents into the old ones, leaving anything renamed or deleted behind as
    an orphan that Foundry still shows.
    """
    if plyvel is None:
        raise RuntimeError("plyvel is not available")
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
            for document in documents:
                primary, children = splitDocument(document, collection)
                for child_collection, child_key, child in children:
                    batch.put(_key(child_collection, child_key), _value(child))
                batch.put(_key(collection, primary.get("_id")), _value(primary))
    finally:
        db.close()
    return path


def readPack(path, collection=None):
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
    children = {}
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
                field = prefix.split(".", 1)[1]
                parent_id = identifier.split(".", 1)[0]
                children.setdefault(parent_id, {}).setdefault(field, []).append(document)
            elif collection is None or prefix == collection:
                primaries[identifier] = document
    finally:
        db.close()

    documents = []
    for identifier, primary in primaries.items():
        owned = children.get(identifier, {})
        for field, entries in owned.items():
            by_id = {entry.get("_id"): entry for entry in entries}
            # Restore the parent's order rather than LevelDB's key order.
            ordered = [by_id[i] for i in primary.get(field, []) if i in by_id]
            # A pack we did not write may not list its children in the parent.
            primary[field] = ordered or entries
        documents.append(primary)
    return documents
