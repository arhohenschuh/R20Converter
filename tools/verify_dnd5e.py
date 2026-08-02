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
