# B064 - Actor resource contracts are incomplete

**Severity:** High
**Status:** Fixed in v1.13.0
**Found:** 2026-08-20 while promoting Gate G29/G31 repairs into the converter

## Defect

`createActorSpells()` always copied Roll20's current remaining count into `system.spells`. That is
correct for a played world, but a module is a fresh adventure source: NPC spellcasters arrived with
partially spent or empty pools. If Roll20 omitted the printed totals, a valid parsed caster level
still produced zero available slots because dnd5e derives capacity but clamps the persisted
`value` to it; it does not fill the pool.

Separately, spell emission had no final resource-contract gate. A positive self `itemUses` target
could reference no root `system.uses` pool, or an ordinary slot spell could charge both that pool
and a spell slot. The documents loaded, but the activity dialog could close without a card or a
resource update.

## Fix contract

- Modules initialize every printed spell-slot pool at capacity; worlds preserve remaining state.
- Module NPCs with no printed pool use the dnd5e 5.3.3 full-caster table and retain derived
  `override: null` semantics.
- Remaining values above capacity are clamped and logged.
- Positive spell self `itemUses` targets require a usable root pool.
- A standard slot spell cannot positively consume that pool and a spell slot on one activity.
- Negative targets that create charges remain valid.
- Existing at-will, ritual, innate, and primary/secondary B062 behavior remains unchanged.

## Regression coverage

`tests/test_dnd5e_schema_diff.py` covers module/world availability, caster-level derivation, and
invalid-source clamping. `tests/test_asset_and_compendium_fixes.py` covers missing pools,
double-consumption rejection, negative charge generation, and B062 preservation. The v1.13.0
shipping suite passes 846 tests. On a real Sunless Citadel module, production Gate G29 passes 2
self-use consumers and G31 passes 5 spellcasters with 6 full slot pools.