# B062 — Compendium overwrite discards source spell casting state

**Severity:** High
**Status:** Fixed in v1.11.2
**Found:** 2026-08-20 while comparing pure R20Converter output with accepted modules

## Defect

With `--no-compendium-overwrite`, a matched spell correctly retained the richer compendium
description and activities, but the entire compendium `system` object also supplied generic
casting defaults. Source-specific `method`, `prepared`, `uses`, and activity consumption were
discarded because spell state was absent from `Item.CHARACTER_STATE_KEYS`.

This converts source-owned spells into a different resource contract:

- innate or at-will spells become ordinary slot casts on Actors with no suitable slots;
- source-prepared character spells become unprepared;
- limited innate use pools disappear;
- secondary compendium activities may consume a spell slot or item use independently.

The document still loads, so the failure appears only when the activity is pressed or when a
prepared-spell gate compares output with the immutable Roll20 row.

## Fix contract

- Preserve source spell `method`, numeric `prepared`, and `uses` under
  `--no-compendium-overwrite` while retaining compendium template data.
- For limited innate spells, copy one source `itemUses` consumer onto a matching primary
  compendium activity and do not charge secondary activities.
- For at-will and ritual-only spells, disable spell-slot consumption on every activity.
- Ordinary slot spells retain the compendium activity's slot consumption.
- Recognize explicit NPC spell names marked “Ritual Only” as native ritual casting.
- Do not pass unknown source fields through the compendium boundary.

## Regression coverage

`tests/test_asset_and_compendium_fixes.py` covers state preservation, limited innate use,
secondary activities, at-will/ritual consumption, ordinary slot consumption, and rejection of
unknown fields. `tests/test_dnd5e_schema_diff.py` covers native at-will and ritual preparation
shapes.