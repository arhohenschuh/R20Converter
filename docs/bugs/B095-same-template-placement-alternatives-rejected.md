# B095 - Same-template placement alternatives are rejected as ambiguous

**Severity:** High
**Status:** Fixed in v1.15.7
**Found:** 2026-08-24 during *Princes of the Apocalypse* v1.15.6 reconversion
**Component:** `src/entities/items.py` (`_alternativePlacementActivities`,
`_mergeSpellConsumption`, `_validateResourceContract`)
**Related:** B077, B082, B083, B092

## Defect

B092 recognizes several complete placement activities as mutually exclusive ways to cast one
limited innate spell. Its safety predicate required every activity to use a distinct
`target.template.type`. That works for *Wall of Fire* (`wall` versus `cylinder`) but rejects
*Wall of Stone*: both valid choices use a `wall` template while their concrete panel geometry is
different.

The Dao casts *Wall of Stone* once per day. The pristine donor provides two complete save
activities:

- `saveWallOfStonII`, **Place Square Panels**: ten 10-by-10-foot panels, 0.5 feet thick;
- `addPlacLongPane1`, **Place Long Panels**: ten 20-by-10-foot panels, 0.25 feet thick.

Both ordinary spell activities consume a spell slot. During innate conversion both must instead
consume one use from the Dao's single 1/day Item pool. Version 1.15.6 raised
`Cannot select one primary donor activity for limited innate spell 'Wall of Stone'` because both
templates have type `wall`.

## Evidence

- Immutable source: `Princes of the Apocalypse_R20Export-1.0.1.zip`, 1,319,787,564 bytes,
  SHA-256 `1244095A20CB78E974C01D781263C6877A1E4A50DBBF7006138829D8A0B9AABF`.
- Source Dao ID: `-KyYf39Ef52odcmJbp1S`; source *Wall of Stone* cadence: `1/Day`.
- Beyond5e donor: `1.1.15-rc.2`, archive SHA-256
  `EEA14D09CF51EB85AB940B24573BDD529768DDF4FA8D3A72E14483958498B1DF`, pristine tree
  SHA-256 `8C61D0F2403ED9513EBBEC608493CDC9AA7EB890F25BA046C40BE04351C242A1`.
- Top-level donor Item: `WallOfStone14III`; Dao embedded Item: `RLtHN5GZbhdaV2HU`.

The conversion-only workaround changed only `addPlacLongPane1` on the top-level donor from
`spellSlot: true` to `false`, making Square Panels the temporary unique primary. After conversion,
both exact embedded donor activities were restored into the emitted Dao. The owner-feedback RC then
passed Gate A 36/0/0/4, native import, Gate B, Gate D 130/130, cleanup persistence, and zero module
migrations. That workaround proves the failure is primary-selection policy rather than malformed
source or donor content.

## Required handling

- Recognize explicit placement choices when their normalized names and complete template geometry
  are both distinct, even when their template types match.
- Keep requiring at least two same-type, slot-consuming activities named `Place ...` with a
  concrete template type.
- Copy the same source Item-use target to every valid placement and retain the one-use pool.
- Continue rejecting repeated placement names, repeated geometry, unnamed duplicate saves,
  transforms, concentration follow-ups, and damage activities.

## Resolution

`_alternativePlacementActivities()` now requires unique normalized placement names and unique
complete template dictionaries instead of unique template-type strings. The existing activity-type,
`Place ...`, spell-slot, and concrete-template guards remain unchanged.

The pristine donor census contains eleven qualifying multi-placement spell groups: ten already
accepted by B092 and exactly one newly admitted group, top-level *Wall of Stone*. A minimized
source-backed conversion using the exact immutable Dao and pristine donor completes without either
B095 shim. Both the Actor pack and native Adventure preserve the two exact activity IDs, distinct
wall geometry, one 1/day pool, and one positive Item-use consumer on each activity.

Regressions cover the exact Square/Long panel pair and require conversion to remain red for either
a repeated placement name or repeated template geometry. The complete Python 3.8 suite passes
927/927.