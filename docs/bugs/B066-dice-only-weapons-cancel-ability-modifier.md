# B066 - Dice-only weapons cancel the ability modifier

**Severity:** Minor
**Status:** Fixed in v1.14.0
**Found:** 2026-08-20 when the real v1.14.0 Sunless control failed Gate G30

## Defect

When a weapon-like attack printed dice but no ability modifier, the converter stored the dice in
`system.damage.base` with a negative bonus equal to the selected ability modifier. dnd5e then added
`@mod`, producing the right numeric total through cancellation. Sunless Citadel's robed Skeleton
Shovel became `1d6 - 2 + @dex.mod`.

The total was correct, but the representation was fragile: changing the Actor's ability changed an
attack whose source explicitly had no modifier. Gate G30 rejects this shape.

## Fix contract

Dice-only weapon damage with a nonzero selected modifier is carried as an explicit attack-activity
damage part with `includeBase: false`. Ordinary weapons whose printed bonus contains their ability
modifier continue to use `system.damage.base` and `includeBase: true`.

## Regression coverage

`tests/test_dnd5e_output.py` pins the explicit carrier and degenerate dice cases.
`tests/test_dnd5e_totals.py` independently computes totals through the declared carrier. All 230
damage-shape and total tests pass, and the real Sunless Gate G30 population is zero.