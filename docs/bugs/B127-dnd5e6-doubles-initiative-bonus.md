# B127: dnd5e 6 doubles the converted initiative bonus

- Severity: Moderate
- Status: Fixed in v1.17.0
- Observed release: R20Converter 1.16.4 output loaded in dnd5e 6.x
- Found: 6 November 2026, from the dnd5e 6.0.6 source during the 6.x target work

## Reproduction

`createAttributeInitiative` wrote the pre-formula shape
`{"value": b, "bonus": b, "mod": m, "prof": p, "total": t}`, with `bonus` as a number.
dnd5e 6.0.6 migrates that source in two steps:

1. `CommonTemplate.#migrateBonusData` copies `attributes.init.bonus` to
   `attributes.init.roll.bonus`.
2. `AttributesFields._migrateInitiative` runs because `init.value` is set and `init.bonus` is not
   a string, and appends `init.value` again.

The result is `roll.bonus = "b + b"`. A +2 Roll20 initiative bonus becomes +4. dnd5e 5.3.3 does not
double it.

The pinned Dragoncoast Danger export has no nonzero extra initiative bonus, so the regression
is synthetic and paired with the source-derived migration.

## Resolution

The builder persists only `{"ability": "", "bonus": "<b>"}` (an empty string for zero). dnd5e
derives the modifier, proficiency, and total. The 6.x target moves the string into
`init.roll.bonus`.

Regression coverage (`tests/test_dnd5e_target.py::TestB127Initiative`) checks +2 and -1: the
old shape yields `"b + b"` under the native migration sequence, while the new shape yields `"b"`
both before and after the 6.x transform. Exported HEAD produces the old shape and `"2 + 2"`.

Pinned export: all 88 actors store `init` as `{ability, roll}` under the 6.x target, and native
dnd5e 6.0.6 initiative totals match HEAD for all 88 actors.

## Already Converted Outputs

Outputs from 1.16.4 and earlier, opened in dnd5e 6.x, double any nonzero extra initiative bonus.
The persisted value depends on whether the world migrated. Check through the post-conversion
workflow.
