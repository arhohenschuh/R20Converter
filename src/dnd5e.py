"""dnd5e system schema constants and shape builders.

Single source of truth for every dnd5e version number and data shape that
R20Converter emits, mirroring the role ``foundry.py`` plays for the Foundry core
schema (see ADR-002). See ADR-008 for why the dnd5e port exists at all.

Every constant here was read out of the dnd5e 5.3.3 source rather than inferred:
``module/config.mjs`` for the enumerations, ``module/data/shared/damage-field.mjs``
for ``DamageData``, ``module/documents/activity/attack.mjs`` for activity shape.
"""

import copy
import hashlib
import re


# --- Target system ---------------------------------------------------------

#: The dnd5e version whose data schema R20Converter writes.
#:
#: This is not decoration. It is written to ``dnd5e.systemMigrationVersion`` and
#: to each document's ``_stats.systemVersion``, and dnd5e reads both to decide
#: whether to migrate. Claiming an older version than we emit runs a migration
#: against documents that have no legacy fields left to convert — which silently
#: empties ``system.damage.base``. Claiming a newer one strands any legacy field
#: we did not port. It must always tell the truth about our output.
SYSTEM_VERSION = "5.3.3"

#: Oldest dnd5e release that understands the schema we emit. Activities landed in
#: dnd5e 4.0; 5.0.0 is the first release of the current generation.
MINIMUM_SYSTEM_VERSION = "5.0.0"


# --- Item type enumerations (config.mjs) -----------------------------------

#: ``CONFIG.DND5E.weaponTypes`` — the values of ``system.type.value`` on a weapon.
WEAPON_TYPES = ("simpleM", "simpleR", "martialM", "martialR", "natural", "improv", "siege")

#: ``CONFIG.DND5E.armorTypes`` — ``system.type.value`` on equipment.
ARMOR_TYPES = ("light", "medium", "heavy", "natural", "shield")

#: ``CONFIG.DND5E.validProperties.weapon`` — the only keys allowed in the
#: ``properties`` **array**. v1.5.6 emitted an object of booleans over a
#: different, partly obsolete key set: ``fir`` and ``spc`` survive, but ``lgt``
#: replaced nothing and ``lod``/``mgc``/``sil``/``ada`` are new.
WEAPON_PROPERTIES = (
    "ada", "amm", "fin", "fir", "foc", "hvy", "lgt", "lod",
    "mgc", "rch", "rel", "ret", "sil", "spc", "thr", "two", "ver",
)

#: ``CONFIG.DND5E.weaponIds`` — legal ``system.type.baseItem`` values.
WEAPON_BASE_ITEMS = (
    "battleaxe", "blowgun", "club", "dagger", "dart", "flail", "glaive", "greataxe",
    "greatclub", "greatsword", "halberd", "handaxe", "handcrossbow", "heavycrossbow",
    "javelin", "lance", "lightcrossbow", "lighthammer", "longbow", "longsword", "mace",
    "maul", "morningstar", "musket", "pike", "pistol", "quarterstaff", "rapier",
    "scimitar", "shortsword", "sickle", "spear", "shortbow", "sling", "trident",
    "warpick", "warhammer", "whip",
)

#: ``CONFIG.DND5E.armorIds``.
ARMOR_BASE_ITEMS = (
    "breastplate", "chainmail", "chainshirt", "halfplate", "hide", "leather", "padded",
    "plate", "ringmail", "scalemail", "splint", "studded",
)

#: Ability keys, in the order used to break ties when several abilities share the
#: modifier baked into a damage formula. Fixed so that output is reproducible:
#: an arbitrary "first match wins" over a dict would vary with insertion order.
ABILITIES = ("str", "dex", "con", "int", "wis", "cha")

#: ``CONFIG.DND5E.SPELL_SLOT_TABLE``. Each row is one full-caster level and
#: each value is the capacity of slot levels 1 through 9. NPCs with a caster
#: level but no printed Roll20 pool need these values to initialize a fresh
#: module; worlds retain their current play state.
SPELL_SLOT_TABLE = (
    (2,), (3,), (4, 2), (4, 3), (4, 3, 2), (4, 3, 3),
    (4, 3, 3, 1), (4, 3, 3, 2), (4, 3, 3, 3, 1),
    (4, 3, 3, 3, 2), (4, 3, 3, 3, 2, 1),
    (4, 3, 3, 3, 2, 1), (4, 3, 3, 3, 2, 1, 1),
    (4, 3, 3, 3, 2, 1, 1), (4, 3, 3, 3, 2, 1, 1, 1),
    (4, 3, 3, 3, 2, 1, 1, 1), (4, 3, 3, 3, 2, 1, 1, 1, 1),
    (4, 3, 3, 3, 3, 1, 1, 1, 1), (4, 3, 3, 3, 3, 2, 1, 1, 1),
    (4, 3, 3, 3, 3, 2, 2, 1, 1),
)


def spellSlots(caster_level):
    """Full-caster slot capacity for ``caster_level`` as ``{level: count}``."""
    try:
        level = int(caster_level)
    except (TypeError, ValueError):
        return {}
    if level <= 0:
        return {}
    row = SPELL_SLOT_TABLE[min(level, len(SPELL_SLOT_TABLE)) - 1]
    return {slot_level: count for slot_level, count in enumerate(row, 1)}


# --- baseItem resolution ---------------------------------------------------

def normalizeItemName(name):
    """Reduce an item name to a comparable key.

    Roll20 names carry qualifiers a slug lookup must ignore: ``"Longsword
    (Melee; Two-Handed)"``, ``"Shortsword +1"``, ``"Dagger, Silvered"``.
    """
    if not name:
        return ""
    name = str(name).lower()
    name = re.sub(r"\([^)]*\)", " ", name)          # parenthetical qualifiers
    name = re.sub(r"[+-]\s*\d+", " ", name)          # magic bonuses
    name = re.sub(r"[^a-z0-9]+", "", name)           # punctuation and spacing
    return name


def _baseItemIndex(slugs):
    return {slug: slug for slug in slugs}


_WEAPON_INDEX = _baseItemIndex(WEAPON_BASE_ITEMS)
_ARMOR_INDEX = _baseItemIndex(ARMOR_BASE_ITEMS)

#: Names that do not normalise onto their slug. Deliberately short and explicit:
#: guessing a baseItem is worse than leaving it empty, because a wrong slug makes
#: dnd5e apply the wrong mastery, properties and proficiency.
_WEAPON_ALIASES = {
    "handcrossbow": "handcrossbow", "crossbowhand": "handcrossbow",
    "lightcrossbow": "lightcrossbow", "crossbowlight": "lightcrossbow",
    "heavycrossbow": "heavycrossbow", "crossbowheavy": "heavycrossbow",
    "lighthammer": "lighthammer", "hammerlight": "lighthammer",
    "warpick": "warpick", "warpickaxe": "warpick", "pickwar": "warpick",
    "greatclub": "greatclub", "quarterstaff": "quarterstaff", "staff": "quarterstaff",
    "shortbow": "shortbow", "bowshort": "shortbow",
    "longbow": "longbow", "bowlong": "longbow",
}

_ARMOR_ALIASES = {
    "chainmail": "chainmail", "chainshirt": "chainshirt", "halfplate": "halfplate",
    "platearmor": "plate", "ringmail": "ringmail", "scalemail": "scalemail",
    "studdedleather": "studded", "studdedleatherarmor": "studded",
    "leatherarmor": "leather", "hidearmor": "hide", "paddedarmor": "padded",
    "splintarmor": "splint", "breastplate": "breastplate",
}


def _candidateKeys(name):
    """Normalised lookup keys to try, most specific first.

    ``"Dagger, Silvered"`` needs the trailing qualifier dropped, but only as a
    *fallback*: trying the whole name first means a genuine comma-containing
    weapon name is never truncated into a wrong match.
    """
    if not name:
        return []
    keys = [normalizeItemName(name)]
    head = str(name).split(",")[0]
    head_key = normalizeItemName(head)
    if head_key and head_key not in keys:
        keys.append(head_key)
    return [k for k in keys if k]


def weaponBaseItem(name):
    """Resolve an SRD weapon slug, or ``""`` when there is no confident match.

    Empty is a legitimate answer — most converted content is bespoke monster
    attacks (``Bite``, ``Tentacles``, ``Corrupting Touch``) with no SRD
    equivalent, and dnd5e accepts an empty ``baseItem``.
    """
    for key in _candidateKeys(name):
        match = _WEAPON_INDEX.get(key) or _WEAPON_ALIASES.get(key)
        if match:
            return match
    return ""


def armorBaseItem(name):
    """Resolve an SRD armor slug, or ``""``."""
    for key in _candidateKeys(name):
        match = _ARMOR_INDEX.get(key) or _ARMOR_ALIASES.get(key)
        if match:
            return match
    return ""


# --- Damage ----------------------------------------------------------------

#: Damage types dnd5e recognises. Roll20 data carries trailing whitespace
#: (``"bludgeoning "``), non-types (``"spell"``, ``"none"``) and compound
#: descriptions (``"bludgeoning or slashing"``); all are normalised or dropped
#: rather than emitted, because an unrecognised type fails schema validation.
DAMAGE_TYPES = (
    "acid", "bludgeoning", "cold", "fire", "force", "lightning", "necrotic",
    "piercing", "poison", "psychic", "radiant", "slashing", "thunder",
)

_DICE_RE = re.compile(r"(\d+)\s*d\s*(\d+)", re.IGNORECASE)
_ADDEND_RE = re.compile(r"([+-])\s*(\d+)\b(?!\s*d\s*\d)", re.IGNORECASE)
ABILITY_MOD_RE = re.compile(r"@abilities\.(str|dex|con|int|wis|cha)\.mod", re.IGNORECASE)
_FORMULA_DICE_RE = re.compile(
    r"\d+\s*d\s*\d+(?:r[oe]?[<>]=?\d+|kh\d*|kl\d*|min\d+|max\d+)*",
    re.IGNORECASE)
_FORMULA_DIE_SUFFIX_RE = re.compile(r"\bd\s*\d+\b", re.IGNORECASE)
_FORMULA_REFERENCE_RE = re.compile(r"@[A-Za-z0-9_.-]+")
_FORMULA_FUNCTION_RE = re.compile(
    r"\b(?:floor|ceil|round|trunc|abs|min|max)\s*(?=\()", re.IGNORECASE)


def isRollFormula(formula):
    """Return whether a string is a plausible Foundry roll formula.

    Roll20 sometimes stores explanatory prose in fields that dnd5e models as a
    FormulaField. Preserve dynamic dice and ``@`` references, but reject bare
    words that make Foundry drop the containing document during initialization.
    """
    text = str(formula or "").strip()
    if not text:
        return True
    text = _FORMULA_DICE_RE.sub(" ", text)
    text = _FORMULA_DIE_SUFFIX_RE.sub(" ", text)
    text = _FORMULA_REFERENCE_RE.sub(" ", text)
    text = _FORMULA_FUNCTION_RE.sub(" ", text)
    return re.search(r"[A-Za-z]", text) is None \
        and re.search(r"[^\d\s+\-*/%().,\[\]{}#|:'\"<>=]", text) is None


def normalizeDamageType(damage_type):
    """Map a Roll20 damage type onto a dnd5e one, or ``None``.

    ``None`` means "emit no type" — which is valid — rather than emitting a
    value the schema will reject.
    """
    if not damage_type:
        return None
    key = str(damage_type).strip().lower()
    if key in DAMAGE_TYPES:
        return key
    # "bludgeoning or slashing" and friends: take the first recognised word so
    # the damage is still typed, rather than dropping the type entirely.
    for word in re.split(r"[^a-z]+", key):
        if word in DAMAGE_TYPES:
            return word
    return None


def damageData(number=None, denomination=None, bonus="", types=None,
               custom_formula=None, scaling_mode="", scaling_number=1,
               scaling_formula=""):
    """Build a dnd5e ``DamageData`` object.

    Replaces the v1.5.6 ``[[formula, type], ...]`` pair list. Shape read from
    ``module/data/shared/damage-field.mjs``: ``types`` is a ``SetField``, so it
    serialises as an array, and ``custom.enabled`` decides whether the dice
    fields or the custom formula are used.
    """
    normalized = []
    for damage_type in (types or []):
        mapped = normalizeDamageType(damage_type)
        if mapped and mapped not in normalized:
            normalized.append(mapped)
    return {
        "number": number,
        "denomination": denomination,
        "bonus": "" if bonus in (None, 0, "0") else str(bonus),
        "types": normalized,
        "custom": {
            "enabled": custom_formula is not None,
            "formula": custom_formula or "",
        },
        "scaling": {
            "mode": scaling_mode,
            "number": scaling_number,
            "formula": scaling_formula,
        },
    }


def parseDamageFormula(formula):
    """Split a Roll20 damage formula into dice, flat bonus and leftovers.

    Returns ``(number, denomination, bonus, remainder)``. ``remainder`` holds
    anything that is not the leading dice term or a plain integer addend — a
    second damage die (``"1d6 + 3 + 1d8"``) or a symbolic modifier
    (``"@abilities.str.mod"``) — so the caller can decide what to do with it
    rather than losing it.

    Degenerate formulas are real and must survive: nets roll ``1d0``, torches
    deal a flat ``1``, and a Gas Spore's touch is ``1d1``.
    """
    text = str(formula or "").strip()
    if not text:
        return None, None, 0, ""

    dice = _DICE_RE.search(text)
    number = denomination = None
    if dice:
        number = int(dice.group(1))
        denomination = int(dice.group(2))
        rest = text[:dice.start()] + " " + text[dice.end():]
    else:
        rest = text

    bonus = 0
    def _takeAddend(match):
        nonlocal bonus
        bonus += (-1 if match.group(1) == "-" else 1) * int(match.group(2))
        return " "
    rest = _ADDEND_RE.sub(_takeAddend, rest)

    # A leading bare integer ("1", "7") is a flat damage value, not an addend.
    if number is None:
        bare = re.fullmatch(r"\s*(\d+)\s*", rest)
        if bare:
            bonus += int(bare.group(1))
            rest = ""

    remainder = re.sub(r"^[\s+]+|[\s+]+$", "", re.sub(r"\s+", " ", rest)).strip("+ ")
    return number, denomination, bonus, remainder


# --- Ability modifier extraction (AD-4) ------------------------------------

class ModifierExtraction(object):
    """How a baked-in ability modifier should be split out of damage.

    dnd5e appends ``@mod`` to weapon damage, resolved from the activity's
    ability. Roll20 bakes that modifier into the damage instead — ``"Bite
    1d10+2"`` where the SRD writes ``"1d10"`` plus the modifier. Attaching a
    default activity without compensating therefore rolls ``1d10+2+mod``.

    The fix moves the modifier out of the damage and into the ability, leaving
    the printed total unchanged while the attack roll gains the modifier it was
    missing. See AD-4.
    """

    __slots__ = ("ability", "bonus", "flat", "remainder")

    def __init__(self, ability, bonus, flat, remainder=""):
        #: Ability key that drives both the attack roll and the damage ``@mod``.
        self.ability = ability
        #: Bonus left on the damage after the modifier was taken out.
        self.bonus = bonus
        #: ``attack.flat``. Always ``False`` from this function — see B005. It
        #: is an *attack-roll* concern (``getAttackData()`` returns only
        #: ``attack.bonus`` when set) and has no effect on damage, so it cannot
        #: be used to suppress ``@mod``.
        self.flat = flat
        #: Formula fragments the caller must preserve (a second damage die).
        self.remainder = remainder

    def __repr__(self):
        return ("ModifierExtraction(ability=%r, bonus=%r, flat=%r, remainder=%r)"
                % (self.ability, self.bonus, self.flat, self.remainder))

    def __eq__(self, other):
        return (isinstance(other, ModifierExtraction)
                and self.ability == other.ability and self.bonus == other.bonus
                and self.flat == other.flat and self.remainder == other.remainder)


def appendsAbilityModifier(is_weapon=True, has_dice=True):
    """Whether dnd5e will append ``@mod`` to this item's damage.

    Read out of ``AttackActivityData#_processDamagePart`` (dnd5e 5.3.3):

    * the block only runs for ``item.type === "weapon"``;
    * within it, ``@mod`` is pushed only when the base part is **not
      deterministic** — a flat ``"1"`` torch gets no modifier, a ``"1d8"``
      sword does.

    Anything else — spells, feats, flat damage — is emitted unchanged, because
    nothing will be added to it.
    """
    return bool(is_weapon) and bool(has_dice)


def extractAbilityModifier(bonus, ability_mods, ranged=False, symbolic=None,
                           remainder="", is_weapon=True, has_dice=True,
                           required=None):
    """Choose the activity's ability and the damage bonus that survives with it.

    ``bonus``        the flat bonus baked into the damage
    ``ability_mods`` ``{"str": 2, "dex": 1, ...}`` for the owning actor
    ``ranged``       picks the natural default when nothing else decides
    ``symbolic``     ability key when the formula said ``@abilities.X.mod``
                     outright; that term is already the ability contribution
    ``remainder``    passed through untouched
    ``is_weapon``    only weapons get an automatic ``@mod``
    ``has_dice``     deterministic damage gets no ``@mod`` either
    ``required``     the ability the caller has *already committed to*, because
                     the attack roll was matched against it. The damage must then
                     be reduced by that ability's modifier and no other — picking
                     a different one here and letting the caller keep its own is
                     how a Goblin ended up rolling ``1d6-1`` for a printed
                     ``1d6+2`` (B025).

    The invariant, in every branch: **the printed total is unchanged.** The
    general rule is ``residual = printed - mod(ability)``, which holds for *any*
    ability; matching the ability to the baked bonus is a refinement that drives
    the residual to zero, which is what the SRD statblock looks like.
    """
    mods = {k: int(v or 0) for k, v in (ability_mods or {}).items()}
    natural = "dex" if ranged else "str"
    bonus = int(bonus or 0)
    appends = appendsAbilityModifier(is_weapon, has_dice)

    # 0. The caller already picked the ability. Honour it: the only correct
    #    residual is the one measured against that ability's modifier.
    if required in ABILITIES and not symbolic:
        if not appends:
            return ModifierExtraction(required, bonus, False, remainder)
        return ModifierExtraction(required, bonus - mods.get(required, 0),
                                  False, remainder)

    # 1. The formula named the ability itself (``@abilities.str.mod``).
    if symbolic:

        key = str(symbolic).lower()
        if key not in ABILITIES:
            raise ValueError("unknown ability %r" % (symbolic,))
        if appends:
            # ``@mod`` will re-add the named modifier, so only the symbolic
            # token is removed. Any other flat addend stays on the damage —
            # dropping it is B001.
            return ModifierExtraction(key, bonus, False, remainder)
        # Nothing will be appended, so the named modifier has to be materialised
        # into the damage or the printed total falls by its value.
        return ModifierExtraction(key, bonus + mods.get(key, 0), False, remainder)

    # 2. No ``@mod`` is coming: spells, feats and flat damage are left alone.
    #    Subtracting here would silently reduce the printed damage (B005).
    if not appends:
        return ModifierExtraction(natural, bonus, False, remainder)

    # 3. An ability whose modifier equals the baked bonus IS the ability the
    #    Roll20 sheet used — the data reveals it, and the residual falls to zero.
    #    Ties resolve by ABILITIES order so the output is deterministic.
    if bonus:
        for key in ABILITIES:
            if key in mods and mods[key] == bonus:
                return ModifierExtraction(key, 0, False, remainder)

    # 4. An ability with a zero modifier keeps ``@mod`` harmless, so the bonus
    #    can stay exactly as printed.
    for key in ABILITIES:
        if mods.get(key) == 0:
            return ModifierExtraction(key, bonus, False, remainder)

    # 5. Otherwise subtract the natural ability's modifier. This preserves the
    #    total for any ability, at the cost of a visible residual.
    return ModifierExtraction(natural, bonus - mods.get(natural, 0), False, remainder)


# --- Activities (AD-3) -----------------------------------------------------

ACTIVITY_ATTACK = "attack"
ACTIVITY_DAMAGE = "damage"
ACTIVITY_SAVE = "save"
ACTIVITY_HEAL = "heal"
ACTIVITY_UTILITY = "utility"

_ID_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"


def activityId(seed):
    """Derive a stable 16-character activity id.

    Deterministic rather than random so that converting the same export twice
    produces byte-identical output, which is what makes a diff between two
    builds meaningful.
    """
    digest = hashlib.sha256(str(seed).encode("utf-8")).digest()
    return "".join(_ID_ALPHABET[b % len(_ID_ALPHABET)] for b in digest[:16])


def weaponRange(value=None, long=None, reach=None, units=""):
    """Build ``system.range`` **for a weapon**.

    ``WeaponData`` declares its own range — ``{value, long, reach, units}`` with
    *numeric* fields — rather than reusing the shared ``RangeField``. Sending the
    shared shape here loses ``long`` and ``reach`` and puts a formula string into
    a ``NumberField``.
    """
    def number(raw):
        try:
            parsed = int(raw)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    return {
        "value": number(value),
        "long": number(long),
        "reach": number(reach),
        "units": units if units in ("ft", "mi", "m", "km") else "ft",
    }


#: ``ConsumptionTargetData.type``. From ``CONFIG.DND5E.activityConsumptionTypes``.
#: ``itemUses`` spends the pool on the parent item; ``activityUses`` spends the
#: activity's own, which is not where we put it.
CONSUMPTION_ITEM_USES = "itemUses"


def consumptionTarget(target_type=CONSUMPTION_ITEM_USES, target="", value="1"):
    """Build one entry of ``consumption.targets``."""
    return {
        "type": target_type,
        "target": target,
        "value": _formula(value) or "1",
        "scaling": {"mode": "", "formula": ""},
    }


def applyActivityMetadata(activity, activation=None, range_=None, duration=None,
                          target=None, uses=None, on_item=False):
    """Copy the activated-effect block onto an activity.

    Only ``SpellData`` keeps ``activation`` / ``range`` / ``duration`` / ``target``
    on the document root. For every other item type those keys are not in the
    schema and Foundry drops them, leaving the activity on its defaults — a
    reaction becomes an action, a 120 ft attack shows "self", the target
    disappears. dnd5e's own migration avoids this by copying the values onto the
    activity (``BaseActivityData.createInitialActivity``); we do the same.

    ``on_item`` says the item root already carries these values, in which case
    ``override`` stays ``False`` and the activity inherits them.

    ``uses`` is never copied. ``ActivitiesTemplate`` puts the pool on the item
    root for every activatable type, so a copy on the activity is a second,
    independent pool that the sheet renders alongside the real one. What the
    activity needs instead is a consumption target pointing at the item's pool —
    without one, using a limited-use item never spends a use.
    """
    override = not on_item
    if activation is not None:
        activity["activation"] = dict(activation)
        activity["activation"]["override"] = override
    if range_ is not None:
        activity["range"] = dict(range_)
        activity["range"]["override"] = override
    if duration is not None:
        activity["duration"] = dict(duration)
        activity["duration"].setdefault("concentration", False)
        activity["duration"]["override"] = override
    if target is not None:
        activity["target"] = copy.deepcopy(target)
        activity["target"]["override"] = override
        activity["target"]["prompt"] = True
    if uses and uses.get("max"):
        consumption = activity.setdefault("consumption", {})
        consumption["targets"] = [consumptionTarget(CONSUMPTION_ITEM_USES)]
    return activity


def _activityBase(activity_id, activity_type, name="", sort=0):
    return {
        "_id": activity_id,
        "type": activity_type,
        "name": name,
        "sort": sort,
        "activation": {"type": "action", "override": False},
        "consumption": {"scaling": {"allowed": False}, "spellSlot": True, "targets": []},
        "duration": {"units": "inst", "concentration": False, "override": False},
        "range": {"units": "self", "override": False},
        "target": {
            "template": {"contiguous": False, "stationary": False, "units": "ft"},
            "affects": {"choice": False},
            "override": False,
            "prompt": True,
        },
        "uses": {"spent": 0, "recovery": []},
    }


def attackActivity(activity_id, ability, ranged=False, classification="weapon",
                   bonus="", flat=False, critical_threshold=None, name="", sort=0):
    """Build an ``attack`` activity.

    ``attack.ability`` drives **both** the attack roll and the damage ``@mod``.

    ``ability`` must be a real ability key. ``"none"`` reads back as ``null`` and
    is documented as making ``@mod`` resolve to 0, but writing it fails schema
    validation and the activity is then silently not created. Suppress the
    modifier with ``flat=True`` instead.
    """
    if ability == "none":
        raise ValueError(
            'attack.ability="none" fails validation on write; pass flat=True instead')
    if ability and ability not in ABILITIES:
        # "STR", "banana" and friends validate no better than "none"; fail here
        # rather than emitting an activity dnd5e will reject.
        raise ValueError("unknown ability %r; expected one of %s" % (ability, ABILITIES))
    activity = _activityBase(activity_id, ACTIVITY_ATTACK, name, sort)
    activity["attack"] = {
        "ability": ability or "",
        "bonus": str(bonus or ""),
        "critical": {"threshold": critical_threshold},
        "flat": bool(flat),
        "type": {"value": "ranged" if ranged else "melee", "classification": classification},
    }
    # includeBase keeps the item's own typed damage as the roll, so the damage
    # lives in exactly one place instead of being duplicated into parts.
    activity["damage"] = {"critical": {"bonus": ""}, "includeBase": True, "parts": []}
    return activity


def saveActivity(activity_id, ability, dc=None, dc_calculation="", damage_parts=None,
                 on_save="half", name="", sort=0):
    """Build a ``save`` activity (spells, breath weapons, traps).

    ``save.dc`` is ``{calculation, formula}`` in 5.3.3 — there is no ``value``,
    and ``damage`` on a save activity has no ``critical``. Both are dropped on
    load, so emitting them just makes the stored document non-native.

    ``on_save`` must be ``"none"`` for a cantrip: dnd5e sets that itself in
    ``SaveActivityData#_preCreate``, but only when the key is absent, and we
    always write one.
    """
    activity = _activityBase(activity_id, ACTIVITY_SAVE, name, sort)
    activity["save"] = {
        "ability": [ability] if ability else [],
        "dc": {"calculation": dc_calculation, "formula": "" if dc is None else str(dc)},
    }
    activity["damage"] = {
        "onSave": on_save,
        "parts": list(damage_parts or []),
    }
    return activity


def damageActivity(activity_id, damage_parts=None, name="", sort=0):
    """Build a bare ``damage`` activity — damage with no attack or save."""
    activity = _activityBase(activity_id, ACTIVITY_DAMAGE, name, sort)
    activity["damage"] = {"critical": {"bonus": ""}, "parts": list(damage_parts or [])}
    return activity


def healActivity(activity_id, healing=None, name="", sort=0):
    """Build a ``heal`` activity."""
    activity = _activityBase(activity_id, ACTIVITY_HEAL, name, sort)
    activity["healing"] = healing or damageData(types=["healing"])
    return activity


def utilityActivity(activity_id, name="", sort=0):
    """Build a ``utility`` activity — an item that does something unrollable."""
    return _activityBase(activity_id, ACTIVITY_UTILITY, name, sort)


# --- Document metadata (AD-5) ----------------------------------------------

def damageScaling(mode="", formula="", denomination=None):
    """Translate a v1.5.6 ``system.scaling`` into a damage part's ``scaling``.

    Mirrors ``BaseActivityData.transformDamagePartData`` in 5.3.3: any mode other
    than ``none`` becomes ``whole``, and when the scaling die matches the damage
    die — or the spell is a cantrip — the increment is expressed as a *number* of
    extra dice rather than a formula.

    Returns ``(scaling_mode, scaling_number, scaling_formula)``.
    """
    if not mode or mode == "none":
        return "", 1, ""
    scaling_formula = formula or ""
    scaling_number = 1
    match = re.match(r"^\s*(\d+)d(\d+)\s*$", scaling_formula, re.IGNORECASE)
    if (match and denomination is not None
            and int(match.group(2)) == denomination) or mode == "cantrip":
        scaling_number = int(match.group(1)) if match else 1
        scaling_formula = ""
    return "whole", scaling_number, scaling_formula


def sourceData(book="", page="", custom="", license_="", rules="2014"):
    """Build ``system.source``.

    v1.5.6 stored a bare string. 5.x uses a ``SourceField`` object, so a string
    is dropped on load and every converted document loses its attribution. The
    free-text Roll20 gives us maps onto ``custom``, which is what dnd5e displays
    when ``book`` is unset.
    """
    return {
        "book": book or "",
        "page": str(page or ""),
        "custom": custom or "",
        "license": license_ or "",
        "revision": 1,
        "rules": rules or "2014",
    }


def stats(core_version, system_version=SYSTEM_VERSION):
    """Build the ``_stats`` block carried by every document.

    dnd5e reads ``_stats.systemVersion`` to decide whether a document needs
    migrating. R20Converter emitted no ``_stats`` at all, which leaves the field
    unset and invites a migration over documents that are already current.
    """
    return {
        "systemId": "dnd5e",
        "systemVersion": system_version,
        "coreVersion": core_version,
        "createdTime": None,
        "modifiedTime": None,
        "lastModifiedBy": None,
        "compendiumSource": None,
        "duplicateSource": None,
        "exportSource": None,
    }


def itemType(value, base_item=""):
    """Build ``system.type``.

    Replaces the separate ``weaponType`` / ``armorType`` / ``consumableType`` /
    ``toolType`` fields and the sibling ``baseItem``, all of which dnd5e 5.x
    folded into this one object.
    """
    return {"value": value or "", "baseItem": base_item or ""}


def properties(flags):
    """Convert a ``{key: bool}`` property map into the 5.x array.

    v1.5.6 emitted every key with a boolean; 5.x expects only the keys that are
    set. Unknown keys are dropped rather than passed through — an invalid
    property fails validation for the whole item.
    """
    if isinstance(flags, dict):
        selected = [k for k, v in flags.items() if v]
    else:
        selected = list(flags or [])
    return [k for k in WEAPON_PROPERTIES if k in selected]


#: ``PhysicalItemTemplate`` weight units, ``module/data/item/templates/physical-item.mjs``.
DEFAULT_WEIGHT_UNITS = "lb"

#: ``PhysicalItemTemplate`` price denomination.
DEFAULT_PRICE_DENOMINATION = "gp"

#: ``EquippableItemTemplate.attunement``. A StringField in 5.x, not the 1.5.6 enum.
ATTUNEMENT_NONE = ""
ATTUNEMENT_REQUIRED = "required"
ATTUNEMENT_OPTIONAL = "optional"

#: 1.5.6 wrote 0/1/2 for not-required / required / attuned.
_LEGACY_ATTUNEMENT = {
    0: ATTUNEMENT_NONE,
    1: ATTUNEMENT_REQUIRED,
    2: ATTUNEMENT_REQUIRED,
}

#: ``EquipmentData`` stealth disadvantage moved into the properties set.
STEALTH_DISADVANTAGE = "stealthDisadvantage"

#: Dex cap by armour category. ``None`` means uncapped; 0 is a real cap of +0,
#: which is why the two cannot be conflated (B033).
ARMOR_DEX_LIMIT = {
    "light": None,
    "medium": 2,
    "heavy": 0,
}


def weightData(value=0, units=DEFAULT_WEIGHT_UNITS):
    """Build ``system.weight``. A bare number fails validation and is reset."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0
    if value == int(value):
        value = int(value)
    return {"value": value, "units": units}


def priceData(value=0, denomination=DEFAULT_PRICE_DENOMINATION):
    """Build ``system.price``."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0
    if value == int(value):
        value = int(value)
    return {"value": value, "denomination": denomination}


def attunement(value):
    """Map a 1.5.6 numeric attunement onto the 5.x string field."""
    if isinstance(value, str):
        return value if value in (ATTUNEMENT_NONE, ATTUNEMENT_REQUIRED,
                                  ATTUNEMENT_OPTIONAL) else ATTUNEMENT_NONE
    return _LEGACY_ATTUNEMENT.get(value, ATTUNEMENT_NONE)


def armorDexLimit(armor_type):
    """Dex cap for an armour category, ``None`` when uncapped.

    Emitting 0 for everything caps every converted armour at +0 dex.
    """
    return ARMOR_DEX_LIMIT.get((armor_type or "").lower(), None)


# ---------------------------------------------------------------------------
# The activated-effect template
#
# dnd5e 4.0 rebuilt the fields every activatable item shares. The shapes below
# are read from ``module/data/shared/*-field.mjs`` in 5.3.3. Getting these wrong
# is quiet rather than loud: Foundry's DataModel drops keys it does not know and
# substitutes initial values for keys it does, so a legacy block does not raise —
# it just leaves the item with no range, no target and no uses.
# ---------------------------------------------------------------------------

#: ``TargetField#template.type`` — an area of effect. Anything here is a
#: template; everything else is an individual target. From
#: ``CONFIG.DND5E.areaTargetTypes``.
AREA_TARGET_TYPES = (
    "circle", "cone", "cube", "cylinder", "line", "radius", "sphere",
    "square", "wall",
)

#: ``TargetField#affects.type``. From ``CONFIG.DND5E.individualTargetTypes``.
INDIVIDUAL_TARGET_TYPES = (
    "self", "ally", "enemy", "creature", "object", "space",
    "creatureOrObject", "any", "willing",
)

#: ``uses.recovery[].period``. From ``CONFIG.DND5E.limitedUsePeriods`` plus the
#: special ``recharge`` handled in ``UsesField.prepareData``. v1.5.6's
#: ``charges`` is **not** among them — in 5.x that is a *consumption* type, not a
#: recovery period, and ``period`` is an unvalidated ``StringField``, so an
#: invalid value is stored and then silently ignored.
RECOVERY_PERIODS = (
    "lr", "sr", "day", "dawn", "dusk", "initiative", "turnStart", "turnEnd",
    "turn", "recharge",
)

#: ``system.activation.type``. From ``CONFIG.DND5E.activityActivationTypes``.
#: v1.5.6 also emitted ``none``, which does not exist in 5.x.
ACTIVATION_TYPES = (
    "action", "bonus", "reaction", "minute", "hour", "day", "longRest",
    "shortRest", "encounter", "turnStart", "turnEnd", "legendary", "mythic",
    "lair", "crew", "special",
)

#: Item types that keep ``activation`` / ``range`` / ``duration`` / ``target`` on
#: the document root. Only ``SpellData`` declares them; ``WeaponData``,
#: ``FeatData``, ``EquipmentData`` and ``ConsumableData`` do not, so for those
#: the values belong on the **activity** or they are dropped on load. The shared
#: ``ActivitiesTemplate`` contributes only ``activities`` and ``uses``.
ROOT_ACTIVATED_TYPES = ("spell",)


#: ``system.range.units`` — ``CONFIG.DND5E.movementUnits`` plus
#: ``CONFIG.DND5E.rangeTypes``. v1.5.6's ``none`` is not among them.
RANGE_UNITS = ("self", "touch", "spec", "any", "ft", "mi", "m", "km")

#: ``system.duration.units`` — ``CONFIG.DND5E.timeUnits`` plus the permanent and
#: special periods.
DURATION_UNITS = (
    "turn", "round", "second", "minute", "hour", "day", "week", "month",
    "year", "disp", "dstr", "perm", "inst", "spec",
)

#: ``system.method`` on a spell. From ``CONFIG.DND5E.spellcasting``. The legacy
#: ``preparation.mode`` values ``prepared`` and ``always`` both collapse onto
#: ``spell``; the distinction moved to the numeric ``prepared`` field.
SPELLCASTING_METHODS = ("atwill", "innate", "ritual", "pact", "spell")

#: ``system.prepared`` on a spell. From ``CONFIG.DND5E.spellPreparationStates``.
SPELL_UNPREPARED = 0
SPELL_PREPARED = 1
SPELL_ALWAYS_PREPARED = 2

#: The five spell components, which 5.x folded into the shared ``properties``
#: set alongside ``ritual`` and ``concentration``.
SPELL_PROPERTIES = ("vocal", "somatic", "material", "concentration", "ritual")

#: ``details.type.value`` on an NPC. From ``CONFIG.DND5E.creatureTypes``.
#: ``CreatureTypeField.value`` is a blank-allowed ``StringField`` with no
#: choices, so an unrecognised value is stored rather than rejected — and then
#: matches nothing when a consumer looks it up.
CREATURE_TYPES = (
    "aberration", "beast", "celestial", "construct", "dragon", "elemental",
    "fey", "fiend", "giant", "humanoid", "monstrosity", "ooze", "plant",
    "undead",
)

#: ``details.type.swarm`` holds a size key, not a size word.
_SWARM_SIZES = {
    "tiny": "tiny", "small": "sm", "medium": "med", "large": "lg",
    "huge": "huge", "gargantuan": "grg",
}


def creatureType(text):
    """Split a Roll20 NPC type line into ``details.type``.

    Roll20 stores the whole phrase — "humanoid (goblinoid)", "swarm of Tiny
    beasts". Writing that into ``value`` keeps it visible on the sheet but makes
    it useless to everything that resolves it against
    ``CONFIG.DND5E.creatureTypes``, so a converted goblin is not a humanoid for
    the purposes of a favored-enemy check or a compendium filter.

    An unrecognised head word goes to ``custom``, which is what dnd5e's own
    type selector does with one.
    """
    result = {"value": "", "subtype": "", "swarm": "", "custom": ""}
    text = (text or "").strip()
    if not text:
        return result

    match = re.match(r"swarms?\s+of\s+(\w+)\s+(.+)$", text, re.IGNORECASE)
    if match:
        result["swarm"] = _SWARM_SIZES.get(match.group(1).lower(), "")
        text = match.group(2).strip()

    match = re.match(r"([^(]*)\(([^)]*)\)", text)
    if match:
        result["subtype"] = match.group(2).strip()
        text = match.group(1).strip()

    head = text.lower().strip(" ,.")
    # "swarm of Tiny beasts" leaves a plural head word behind.
    if head.endswith("s") and head[:-1] in CREATURE_TYPES:
        head = head[:-1]
    if head in CREATURE_TYPES:
        result["value"] = head
    elif head:
        result["custom"] = text.strip(" ,.")
    return result


def _formula(value):
    """Render a value for a ``FormulaField``, which stores strings.

    ``None`` and ``0`` both mean "unset" in the Roll20 data we are handed, and
    both must come out as ``""`` — a literal ``"0"`` range reads as a real range
    of zero feet and hides the item from the sheet's range column.
    """
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        return ""
    return str(value)


def activationData(activation_type="", value=None, condition=""):
    """Build ``system.activation``.

    v1.5.6 called the scalar ``cost``; 5.x calls it ``value``. The rename is not
    cosmetic — ``cost`` is dropped on load, which silently turns "3 actions" into
    "action". v1.5.6's ``none`` type does not exist in 5.x; it means "not
    activated", which 5.x spells as the empty string. ``special`` *does* exist
    and must be preserved.
    """
    if activation_type not in ACTIVATION_TYPES:
        activation_type = ""
    return {
        "type": activation_type,
        "value": value if isinstance(value, int) and value > 0 else None,
        "condition": condition or "",
    }


def rangeData(value=None, units="", special=""):
    """Build ``system.range``.

    ``long`` is gone in 5.x. ``units`` is ``required, blank: false``, so an empty
    or unrecognised string is invalid and falls back to the field initial — we
    resolve it here rather than let that happen by accident.
    """
    if units not in RANGE_UNITS:
        units = "self"
    return {
        "value": _formula(value) if units in ("ft", "mi", "m", "km") else "",
        "units": units,
        "special": special or "",
    }


def durationData(value=None, units="", special=""):
    """Build ``system.duration``. ``units`` is ``blank: false``; the 5.x initial
    is ``"inst"``, which is also the right reading of "no duration given"."""
    if units not in DURATION_UNITS:
        units = "inst"
    scalar = units in ("turn", "round", "second", "minute", "hour", "day",
                       "week", "month", "year")
    return {
        "value": _formula(value) if scalar else "",
        "units": units,
        "special": special or "",
    }



def targetData(target_type="", size=None, width=None, units="",
               affects_count=None, affects_type="", special=""):
    """Build ``system.target``.

    v1.5.6 stored one flat ``{value, width, units, type}``. 5.x splits it in two:
    an area ``template`` and an ``affects`` count of individuals. Which half a
    legacy value belongs in is decided by the type, not by the caller.
    """
    target_type = target_type or ""
    template = {
        "count": "",
        "contiguous": False,
        "stationary": False,
        "type": "",
        "size": "",
        "width": "",
        "height": "",
        "units": units or "ft",
    }
    affects = {
        "count": "",
        "type": "",
        "choice": False,
        "special": special or "",
    }
    if target_type in AREA_TARGET_TYPES:
        template["type"] = target_type
        template["size"] = _formula(size)
        template["width"] = _formula(width)
    elif target_type in INDIVIDUAL_TARGET_TYPES:
        affects["type"] = target_type
        affects["count"] = _formula(size)
    elif target_type:
        # An unrecognised type is not passed through: an invalid enum value
        # fails validation for the whole document.
        affects["special"] = special or target_type
    return {"template": template, "affects": affects}


def recovery(period="", formula=""):
    """Build one entry of ``uses.recovery``."""
    if period not in RECOVERY_PERIODS:
        return None
    entry = {
        "period": period,
        "type": "recoverAll",
        "formula": "",
    }
    if period == "recharge":
        # A recharge is "regain on a d6 roll of N or higher"; dnd5e stores N in
        # `formula` and recovers everything when it succeeds.
        entry["formula"] = _formula(formula)
    elif formula:
        entry["type"] = "formula"
        entry["formula"] = _formula(formula)
    return entry


def usesData(spent=0, maximum=None, recoveries=None):
    """Build ``system.uses``.

    v1.5.6 stored *remaining* uses in ``value`` and the reset period in ``per``.
    5.x stores *spent* uses and a list of recovery rules. Passing the old shape
    through leaves every limited-use item at zero uses.
    """
    return {
        "spent": spent if isinstance(spent, int) and spent > 0 else 0,
        "max": _formula(maximum),
        "recovery": [r for r in (recoveries or []) if r],
    }


def usesFromLegacy(value=0, maximum=0, per=""):
    """Translate the v1.5.6 ``{value, max, per}`` triple into 5.x ``uses``.

    ``value`` was uses *remaining*, so ``spent = max - value``.
    """
    try:
        maximum_int = int(maximum)
    except (TypeError, ValueError):
        maximum_int = 0
    try:
        value_int = int(value)
    except (TypeError, ValueError):
        value_int = 0
    spent = max(0, maximum_int - value_int) if maximum_int else 0
    period = per if per in RECOVERY_PERIODS else ""
    entry = recovery(period) if period else None
    return usesData(spent, maximum_int or None, [entry] if entry else [])


def spellProperties(vocal=False, somatic=False, material=False,
                    concentration=False, ritual=False):
    """Build a spell's ``system.properties`` set.

    v1.5.6 kept these as a ``components`` object of booleans; 5.x folds them into
    the same ``properties`` array every other item type uses.
    """
    flags = {
        "vocal": vocal,
        "somatic": somatic,
        "material": material,
        "concentration": concentration,
        "ritual": ritual,
    }
    return [k for k in SPELL_PROPERTIES if flags[k]]


def spellPreparation(mode="", prepared=False):
    """Translate the v1.5.6 ``preparation`` object into 5.x ``method``/``prepared``.

    Returns the two keys as a fragment so callers can splice it into ``system``.
    """
    mode = mode or ""
    if mode in ("prepared", "always", ""):
        method = "spell"
    elif mode in SPELLCASTING_METHODS:
        method = mode
    else:
        method = "spell"
    if mode == "always":
        state = SPELL_ALWAYS_PREPARED
    elif prepared:
        state = SPELL_PREPARED
    else:
        state = SPELL_UNPREPARED
    # An innate or at-will spell is always castable; leaving it "unprepared"
    # greys it out on the sheet.
    if method in ("innate", "atwill", "pact") and state == SPELL_UNPREPARED:
        state = SPELL_PREPARED
    return {"method": method, "prepared": state}

