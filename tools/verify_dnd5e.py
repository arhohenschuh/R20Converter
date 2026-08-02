"""Read back a converted world or module and report its dnd5e schema state.

Unit tests assert on Python dicts. They cannot see that the emitter skipped a
field on one code path, that a whole item type kept a legacy shape, or that
Foundry's storage layer dropped something. This reads the **emitted** NeDB files
and measures what actually landed.

That distinction is not academic: the R2 unit suite was 307-green while the
converter was still emitting ``system.scaling``, ``system.components``,
``system.preparation``, ``system.consume``, a flat ``target``, a legacy ``uses``
and ``activation.cost`` on every item. The first run of this script found all of
it (ROADMAP B006-B010).

Usage::

    python tools/verify_dnd5e.py path/to/world [--json]

Exit status is non-zero when a check fails, so it can gate a release.
"""

import argparse
import json
import os
import re
import sys
from collections import Counter

# Fields dnd5e ~1.5.6 wrote that 5.x does not read. Foundry drops unknown keys
# silently, so their presence is invisible in the UI and fatal to the data.
LEGACY_ITEM_FIELDS = (
    "weaponType", "armorType", "consumableType", "toolType", "actionType",
    "attackBonus", "chatFlavor", "critical", "formula", "scaling", "ability",
    "components", "preparation", "consume", "recharge",
)

#: Only ``SpellData`` declares these at the document root.
ROOT_ONLY_ON_SPELLS = ("activation", "target", "duration")

ROLLABLE_TYPES = ("weapon", "spell", "feat", "consumable")

EXPECTED_SYSTEM_VERSION = "5.3.3"

# Roll20 leaves the stat block's own text in the item description. That text is
# an *independent* oracle: it was written by the module author, not by the
# converter, so comparing against it cannot ratify a bug the way a test that
# recomputes the implementation's own logic can.
#   "<em>Melee Weapon Attack </em>+4, Reach 5 ft. <em>Hit : </em>11 (2d8+2) piercing"
PRINTED_TOHIT = re.compile(r"(?:Weapon|Spell) Attack\s*</em>\s*([+-]\s*\d+)", re.I)
PRINTED_DAMAGE = re.compile(r"Hit\s*:?\s*</em>\s*\d+\s*\((\d+)d(\d+)\s*([+-]\s*\d+)?\)", re.I)


def parseSigned(raw):
    if not raw:
        return 0
    return int(raw.replace(" ", ""))


def damageOracle(items, report):
    """Compare each weapon against the to-hit and damage printed in its own text.

    dnd5e appends the activity ability's modifier to a weapon's damage and to its
    attack roll. So the converter must *remove* the modifier Roll20 baked into
    the printed numbers — and remove it exactly once. Getting that wrong is
    invisible in the stored document and only shows up as a wrong number at the
    table.
    """
    checked = 0
    wrong = []
    for item, mods, prof in items:
        if item.get("type") != "weapon":
            continue
        text = item.get("system", {}).get("description", {}).get("value", "") or ""
        activities = item.get("system", {}).get("activities") or {}
        activity = next(iter(activities.values()), None)
        if not activity or activity.get("type") != "attack":
            continue
        ability = activity.get("attack", {}).get("ability") or ""
        mod = mods.get(ability, 0)

        hit = PRINTED_TOHIT.search(text)
        if hit:
            printed = parseSigned(hit.group(1))
            bonus = activity["attack"].get("bonus") or "0"
            try:
                bonus = int(bonus)
            except ValueError:
                bonus = None
            if bonus is not None:
                # dnd5e rolls d20 + mod + proficiency + bonus.
                rolled = mod + (prof if item["system"].get("proficient") else 0) + bonus
                checked += 1
                if rolled != printed:
                    wrong.append("%s to-hit printed %+d, dnd5e rolls %+d"
                                 % (item.get("name"), printed, rolled))

        dmg = PRINTED_DAMAGE.search(text)
        base = item["system"].get("damage", {}).get("base", {})
        if dmg and base.get("denomination") and not base.get("custom", {}).get("enabled"):
            printedBonus = parseSigned(dmg.group(3))
            try:
                storedBonus = int(base.get("bonus") or 0)
            except ValueError:
                storedBonus = None
            if storedBonus is not None and int(dmg.group(1)) == base.get("number") \
                    and int(dmg.group(2)) == base.get("denomination"):
                checked += 1
                # dnd5e appends @mod to a weapon's damage, so the stored bonus
                # plus the ability modifier must reproduce the printed bonus.
                if storedBonus + mod != printedBonus:
                    wrong.append("%s damage printed %+d, dnd5e rolls %+d"
                                 % (item.get("name"), printedBonus, storedBonus + mod))

    if not checked:
        report.check(False, "damage oracle ran", "no printed stat blocks found")
        return
    report.check(not wrong, "printed to-hit and damage match what dnd5e will roll",
                 "%d checks, %d wrong" % (checked, len(wrong)))
    for line in wrong[:10]:
        report.note(line)


def abilityMods(actor):
    """Recompute each ability modifier from the stored score.

    Read from the score rather than from any stored ``mod``, because 5.x does not
    store one — and because a converter that got the modifier wrong would
    otherwise be checked against its own mistake.
    """
    mods = {}
    for key, values in (actor.get("system", {}).get("abilities") or {}).items():
        score = values.get("value")
        if isinstance(score, int):
            mods[key] = (score - 10) // 2
    return mods



def loadDb(path):
    if not os.path.exists(path):
        return []
    documents = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                documents.append(json.loads(line))
    return documents


def collect(root):
    data = os.path.join(root, "data")
    if not os.path.isdir(data):
        data = root
    actors = loadDb(os.path.join(data, "actors.db"))
    items = list(loadDb(os.path.join(data, "items.db")))
    for actor in actors:
        items.extend(actor.get("items", []))
    return actors, items


def ownedItems(actors):
    """Each owned item paired with its actor's ability modifiers and proficiency.

    The damage oracle needs the actor, because dnd5e adds the *actor's* ability
    modifier to the item's damage. A world item has no actor and is skipped.
    """
    rows = []
    for actor in actors:
        mods = abilityMods(actor)
        prof = actor.get("system", {}).get("attributes", {}).get("prof")
        if not isinstance(prof, int):
            prof = 2
        for item in actor.get("items", []):
            rows.append((item, mods, prof))
    return rows


class Report(object):
    def __init__(self):
        self.failures = []
        self.lines = []

    def check(self, ok, label, detail=""):
        self.lines.append("  %-4s %s%s" % ("ok" if ok else "FAIL", label,
                                           (" - %s" % detail) if detail else ""))
        if not ok:
            self.failures.append(label)

    def note(self, text):
        self.lines.append("       %s" % text)


def verify(root):
    actors, items = collect(root)
    report = Report()

    # Non-vacuity first. A suite that scans zero documents and reports PASS is
    # worse than no suite.
    report.check(bool(actors), "actors present", "%d" % len(actors))
    report.check(bool(items), "items present", "%d" % len(items))
    if not items:
        return report, {}

    legacy = Counter()
    for item in items:
        system = item.get("system", {})
        for field in LEGACY_ITEM_FIELDS:
            if field in system:
                legacy["%s (%s)" % (field, item.get("type"))] += 1
        damage = system.get("damage")
        if isinstance(damage, dict) and "parts" in damage:
            legacy["damage.parts"] += 1
        if isinstance(system.get("properties"), dict):
            legacy["properties as object"] += 1
        if isinstance(system.get("type"), str) and item.get("type") != "loot":
            legacy["type as string"] += 1
        if item.get("type") != "spell":
            for field in ROOT_ONLY_ON_SPELLS:
                if field in system:
                    legacy["root %s on %s" % (field, item.get("type"))] += 1
    report.check(not legacy, "no legacy fields emitted")
    for key, count in sorted(legacy.items()):
        report.note("%s x%d" % (key, count))

    documents = items + actors
    stamped = [d for d in documents
               if d.get("_stats", {}).get("systemVersion") == EXPECTED_SYSTEM_VERSION]
    report.check(len(stamped) == len(documents),
                 "_stats.systemVersion == %s everywhere" % EXPECTED_SYSTEM_VERSION,
                 "%d/%d" % (len(stamped), len(documents)))

    # The real invariant is not "everything has an activity" - passive traits
    # correctly have none - but "nothing activated lacks one".
    orphans = [i.get("name") for i in items
               if not i.get("system", {}).get("activities")
               and i.get("system", {}).get("activation", {}).get("type")]
    report.check(not orphans, "no activated item lacks an activity",
                 "%d orphans" % len(orphans))

    mismatched = 0
    defaults = 0
    for item in items:
        for key, activity in (item.get("system", {}).get("activities") or {}).items():
            if activity.get("_id") != key or len(key) != 16:
                mismatched += 1
            if item.get("type") != "spell" \
                    and activity.get("activation", {}).get("override") is False:
                defaults += 1
    report.check(mismatched == 0, "activity ids match their keys")
    report.check(defaults == 0,
                 "non-spell activities carry their own metadata",
                 "%d left inheriting a root block that does not exist" % defaults)

    weapons = [i for i in items if i.get("type") == "weapon"]
    if weapons:
        armed = [w for w in weapons
                 if w["system"].get("damage", {}).get("base", {}).get("denomination")]
        report.check(len(armed) == len(weapons), "weapons have dice in damage.base",
                     "%d/%d" % (len(armed), len(weapons)))
        shaped = [w for w in weapons
                  if set(w["system"].get("range", {}))
                  == {"value", "long", "reach", "units"}]
        report.check(len(shaped) == len(weapons), "weapons use the WeaponData range",
                     "%d/%d" % (len(shaped), len(weapons)))

    damageOracle(ownedItems(actors), report)

    summary = {
        "actors": len(actors),
        "items": len(items),
        "types": dict(Counter(i.get("type") for i in items)),
        "rollableWithActivity": sum(
            1 for i in items
            if i.get("type") in ROLLABLE_TYPES and i["system"].get("activities")),
        "legacyFields": dict(legacy),
    }
    return report, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", help="converted world or module directory")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="print the summary as JSON")
    args = parser.parse_args(argv)

    report, summary = verify(args.path)
    if args.as_json:
        print(json.dumps({"summary": summary, "failures": report.failures}, indent=2))
    else:
        print("dnd5e %s schema check - %s" % (EXPECTED_SYSTEM_VERSION, args.path))
        for line in report.lines:
            print(line)
        print("\n  %s" % ("PASS" if not report.failures
                          else "FAIL (%d)" % len(report.failures)))
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
