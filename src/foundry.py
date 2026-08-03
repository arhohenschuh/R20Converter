"""Foundry VTT platform constants.

Single source of truth for every Foundry version number, compatibility range and
manifest-schema constant that R20Converter emits. See ADR-002.

These values used to be string literals scattered across ``world.py``,
``module.py``, ``R20Converter.py`` and ``entities/settings.py``. They drifted:
``world.json`` claimed core 9.245 with a *compatible* core of 1.0.0 (lower than
the core version it claimed to be written by), while ``module.json``
independently claimed a minimum core of 0.7.5. Collecting them here means the
next Foundry generation bump is one reviewable edit rather than an archaeology
exercise.

The dnd5e *system* schema has the same treatment in ``dnd5e.py`` (ADR-008); the
system version constants below are re-exported from there so the two cannot
drift apart.
"""

import dnd5e

# --- Target platform -------------------------------------------------------

#: Foundry generation we target. Used as ``compatibility.minimum``; a bare major
#: version means "any build of this generation".
MINIMUM_CORE_VERSION = "13"

#: Most recent Foundry build the output has been checked against. Used as
#: ``compatibility.verified``. Foundry warns but does not block above this, so it
#: is safe for this to lag slightly behind the newest release.
#:
#: Set to 14 on the evidence of a document-level comparison against a
#: hand-repaired *Lost Mine of Phandelver* module that runs on Foundry 14.365
#: with dnd5e 5.3.3: across every actor matched by name the converter's output
#: carried the same values, and the only differences were fields where the
#: converter is now the more correct of the two (see B043). This is a
#: compatibility claim, not a schema claim — ``DOCUMENT_SCHEMA_CORE_VERSION``
#: below is what describes the shape we emit, and it stays at 13.
VERIFIED_CORE_VERSION = "14"

#: The core version whose *document schema* we emit, written to
#: ``world.json``'s ``coreVersion``.
#:
#: This is not decoration: Foundry compares it against the running version to
#: decide which document migrations to run. It must always describe the schema
#: we actually produce. Claiming a newer version than we emit makes Foundry skip
#: migrations it would otherwise run; claiming an older one makes it run
#: migrations that no longer exist (see ADR-002). Keep it in step with the
#: document schema port.
DOCUMENT_SCHEMA_CORE_VERSION = "13"

#: Version stamped on the generated world/module package itself. Unrelated to
#: the Foundry version.
PACKAGE_VERSION = "1.0.0"

#: Author recorded on generated packages.
PACKAGE_AUTHOR = "R20Converter"


# --- Manifest schema -------------------------------------------------------

#: Package ``type`` discriminators. Required in the manifest since v10; Foundry
#: no longer infers the package type from the file name.
PACKAGE_TYPE_WORLD = "world"
PACKAGE_TYPE_MODULE = "module"

#: Default game system assumed when none is given.
DEFAULT_GAME_SYSTEM = "dnd5e"

#: The dnd5e system version whose data schema R20Converter writes. Used as the
#: fallback ``systemVersion`` when the system is not installed locally and its
#: real version cannot be read from its ``system.json``, and as the recorded
#: ``dnd5e.systemMigrationVersion`` so the system does not migrate documents that
#: are already current.
#:
#: This must stay in step with ``dnd5e.SYSTEM_VERSION`` and with the documents we
#: actually emit (ADR-008). Claiming an older version runs a migration against
#: documents that have no legacy fields left to convert, which silently empties
#: ``system.damage.base``; claiming a newer one strands any legacy field that was
#: not ported. Both directions corrupt.
DEFAULT_SYSTEM_VERSION = dnd5e.SYSTEM_VERSION

#: Oldest dnd5e release that understands the schema we emit. Activities landed in
#: dnd5e 4.0, and the shapes here are the 5.x generation.
MINIMUM_SYSTEM_VERSION = dnd5e.MINIMUM_SYSTEM_VERSION


def compatibility(minimum=MINIMUM_CORE_VERSION, verified=VERIFIED_CORE_VERSION):
    """Build a v13 ``compatibility`` object.

    Replaces the ``minimumCoreVersion``/``compatibleCoreVersion`` pair, which
    was deprecated in v10 and removed in v13.

    ``maximum`` is deliberately omitted: it *blocks* installation above the
    given version, and we have no reason to forbid a Foundry generation we have
    simply not tested yet.
    """
    return {"minimum": minimum, "verified": verified}


def systemRelationship(system_id, system_version=None):
    """Build the ``relationships.systems`` entry for the game system.

    Replaces the v9 top-level ``dependencies`` array, removed in v13.

    For dnd5e a ``minimum`` is declared as well as a ``verified``: the documents
    we emit use the 5.x schema and are unreadable by older releases (ADR-008), so
    installing against one should fail loudly rather than produce a world full of
    items the system cannot parse.
    """
    relationship = {"id": system_id, "type": "system"}
    compatibility = {}
    if system_id == DEFAULT_GAME_SYSTEM:
        compatibility["minimum"] = MINIMUM_SYSTEM_VERSION
    if system_version:
        compatibility["verified"] = system_version
    if compatibility:
        relationship["compatibility"] = compatibility
    return relationship
