# B077 - Donor activity mismatch drops a limited innate consumer

**Severity:** High
**Status:** Fixed in v1.15.0
**Found:** 2026-08-20 during Tomb of Annihilation v1.14.0 Gate D
**Component:** `src/entities/items.py` (`_mergeSpellConsumption`)
**Related:** B029, B062, B064

## Defect

When source cadence is merged into a richer compendium spell, `_mergeSpellConsumption()` copies
the source `itemUses` target only to a donor activity of the same type. It falls back to the sole
donor activity only when the donor has exactly one. If the source has a utility consumer and the
donor has multiple richer activities of other types, no primary activity is selected.

The function then correctly disables spell-slot consumption on every donor activity, but leaves
all activity target lists empty. The Item retains its daily pool while using it never spends a
charge. The existing resource validator is vacuous here because it validates consumers that exist;
it does not require a limited innate spell to have one.

## Evidence

The dnd5e 5.3.3 Plane Shift donor has `attack` and `save` activities. Five Tomb of Annihilation
Actors (Widow Groat, Peggy Deadbells, Dao, Baggy Nanna, and Gray Slaad) retained valid 1/day or
2/day pools, but both donor activities had `spellSlot: false` and zero `itemUses` targets. Live use
of Dao's primary activity left the pool unchanged.

A minimal call to `_mergeSpellConsumption()` with one source utility consumer and those two donor
activity types reproduces the same output: both donor activities become non-slot activities and
both retain empty target arrays.

## Fix contract

- If source data carries a positive self-use consumer, select one deterministic primary donor
  activity even when activity types differ; prefer the canonical primary ID when present.
- Copy exactly one bounded source consumer onto that primary activity and keep secondary donor
  activities from double-spending.
- Fail closed when a safe primary cannot be selected.
- Extend the final resource contract so a limited innate spell cannot pass with zero positive
  self-use consumers.

## Regression coverage required

Add a multi-activity Plane Shift shape (`utility` source versus `attack` + `save` donor), prove one
charge is spent by the selected primary, prove secondary activities do not double-spend, and keep
the existing same-type and single-donor-activity cases green.

## Resolution

`_mergeSpellConsumption()` selects one same-type donor when unique, then canonical
`dnd5eactivity000`, then a sole donor activity; unresolved ambiguity aborts. The final resource
validator requires exactly one positive self `itemUses` target on every limited innate spell.
`tests/test_asset_and_compendium_fixes.py` includes the Plane Shift attack/save reproducer and keeps
all prior B050/B062 cases green.