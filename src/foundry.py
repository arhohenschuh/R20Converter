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
"""

# --- Target platform -------------------------------------------------------

#: Foundry generation we target. Used as ``compatibility.minimum``; a bare major
#: version means "any build of this generation".
MINIMUM_CORE_VERSION = "13"

#: Most recent Foundry build the output has been checked against. Used as
#: ``compatibility.verified``. Foundry warns but does not block above this, so it
#: is safe for this to lag slightly behind the newest release.
VERIFIED_CORE_VERSION = "13"

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
#: ``dnd5e.systemMigrationVersion`` so the system runs its own migrations from
#: the right starting point.
DEFAULT_SYSTEM_VERSION = "1.5.6"


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
    """
    relationship = {"id": system_id, "type": "system"}
    if system_version:
        relationship["compatibility"] = {"verified": system_version}
    return relationship
