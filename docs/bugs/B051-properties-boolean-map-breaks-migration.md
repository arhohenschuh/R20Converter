# B051: `system.properties` shipped as a boolean map breaks item migration

- **Status**: **Not a defect in converter 1.7.3.** Legacy data defect in packs built by
  older converters. Repaired in place; a regression test guards the current behaviour.
- **Severity**: High — items fail validation and are reported only as a console *warning*
- **Found**: 2026-08-05, running QA Gate B against the shipped adventure modules
- **Component**: `src/dnd5e.py` `properties()` (already correct), pack data

## Symptom

On world load, dnd5e logs — as a **warning**, not an error, and without throwing:

```
TypeError: Failed data migration for Item5e:
    source.system.properties?.findSplice is not a function
  at AttackActivity.transformDurationData
  at AttackActivity.createInitialActivity
  at ActivitiesTemplate.initializeActivities
  at Item5e.migrateData
DataModelValidationFailure
```

The item then fails validation. Nothing surfaces in the UI and nothing fails a file scan.

## Cause

dnd5e ≤ 2.x stored item properties as a boolean map:

```json
"properties": {"amm": false, "hvy": true, "fin": false, "two": true}
```

dnd5e 3.0+ stores an array of the keys that are set, and calls `Array#findSplice` on the
**raw source** during the legacy → Activities migration. A plain object has no
`findSplice`, so migration throws.

## Scope, measured

| Pack | Items affected | Converter generation |
|---|---:|---|
| `out-of-the-abyss` | **1048** | older |
| `dragons-of-icespire-peak` | **786** | older |
| `lost-mine-of-phandelver` | **126** | older |
| `the-shattered-obelisk` | 0 | emits dnd5e 5.x natively (ADR-008) |
| `wardens-of-the-north-season-3` | 0 | 1.7.3 |
| `dragoncoast-danger` | 0 | 1.7.3 |

All affected items are `weapon`. The correlation with converter generation is exact.

## Why the converter is not at fault

`src/dnd5e.py` already normalises this:

```python
def properties(flags):
    if isinstance(flags, dict):
        selected = [k for k, v in flags.items() if v]
    else:
        selected = list(flags or [])
    return [k for k in WEAPON_PROPERTIES if k in selected]
```

It accepts the legacy map *and* an array, and emits an array of known keys. The three
affected packs predate that code. **Do not "fix" `properties()`** — it is the reason the
current output is clean.

## Repair for already-shipped packs

`Foundry_Pipeline_Build\_tools\qa\qa-fix-properties-shape.mjs --pack <dir> [--apply]`

Converts the map to the array of true keys, in world NeDB, world LevelDB and module
packs alike. Applied to the three packs above (1,960 items) and re-verified live: 0
migration failures.

## Guards added

- **Gate A / G18** — `system.properties` is an array, not a boolean map. Offline, so it
  catches this before a build is ever launched.
- **Gate B / L11** — no data-migration failures on load, matching
  `/Failed data migration|DataModelValidationFailure/` against **`console.warn`**.

> The second guard is the important one. The first version of Gate B watched
> `console.error` only and reported **13 PASS / 0 FAIL** on a build with 128 broken
> items. dnd5e never raises this to `error` and never throws.
