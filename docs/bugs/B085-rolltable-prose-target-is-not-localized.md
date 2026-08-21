# B085 - RollTable prose target is not localized

**Severity:** High
**Status:** Fixed in v1.15.2
**Found:** 2026-08-20 during Eberron Setting v1.0.0 finalization
**Component:** `src/R20Converter.py` and `src/module_assembly.py`
**Related:** B065, B071, B075

## Defect

The custom compendium loader retains only document types used for Actor/Item matching. It loads but
then discards a pack declared as `RollTable`. Module assembly's UUID patterns likewise accept only
Actor and Item targets.

Beyond5e's Confusion spell includes a prose link to
`Compendium.beyond5e-2014-compendium.rolltable-1-roll-tables.RollTable.2jNLXURpXnJwFnEJ`.
The local module contains Confusion as two Actor-owned spells and one standalone Item, but all three
descriptions retain the build-time donor UUID. The Adventure snapshot repeats those links.

## Fix contract

- Read a custom module's declared pack types and retain RollTable packs under a supplemental donor
  role without changing existing Actor/Item lookup precedence.
- Index RollTable donors by their full Foundry UUID.
- Clone a referenced RollTable once into `converter.tables`, clear its external folder, and rewrite
  prose to `Compendium.<module>.tables.RollTable.<id>`.
- Include the cloned table in the Adventure and recommendation scan.
- Continue ignoring unrelated unsupported custom pack types.

## Regression coverage required

A declared RollTable document must classify as a supplemental donor while a JournalEntry does not.
An external RollTable prose link must clone exactly one table and rewrite to the local tables pack.

## Resolution

Custom loading records each pack's declared document type and retains RollTables under the
`rolltables` donor bucket. Module assembly now indexes, clones, rewrites, and validates RollTable
targets alongside Actor and Item targets. Focused loader and assembly regressions cover both
boundaries.