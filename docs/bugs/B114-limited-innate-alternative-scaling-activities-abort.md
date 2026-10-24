# B114: Limited innate spell aborts on alternative scaling donor activities

- Severity: High
- Status: Fixed in v1.16.2 for complete casting alternatives; ambiguous shapes remain fail-closed
- Observed release: R20Converter 1.16.1, commit cbb0d0e7a9665c43f780c26d3f31ef98f853454d
- Reported: 24 October 2026, Dragoncoast Danger played-world reconversion (`dcd/v130`)

## Reproduction

Convert with `--custom-compendium` pointing at Beyond5e 1.6.60 (published archive SHA-256
`970843074EE3E4675AD9537884998F6A2FF8466FC2B7EF8789451E6D10E6A00A`) a source NPC that casts
Flame Strike as a limited innate spell. Dragoncoast Danger NPC Sheela Peryroyl has Flame
Strike as `innate = "1/day each"`. The whole conversion aborts:

```text
ValueError: Cannot select one primary donor activity for limited innate spell 'Flame Strike'
  items.py line 269, in _mergeSpellConsumption
```

## Cause

Beyond5e 1.6.x spells built for dnd5e 6.x can carry several complete, mutually exclusive
casting activities that differ only by the caster's choice. Flame Strike `FlameStrike14III`
has two `save` activities, `Fire Scaling` and `Radiant Scaling`, both `spellSlot: true`.
`_selectPrimarySpellActivities` accepts only one slot consumer, a canonical
`dnd5eactivity000`, placement choices named `Place …`/`Create …`, or title-labelled
`<choice>: Initial Save` pairs. Alternative casting choices with other labels match none of
these patterns, so the merge raises.

A read-only scan of all 493 Beyond5e 1.6.60 top-level spell donors finds the same selector
failure for 8 spells: Alter Self, Booming Blade, Destructive Wave, Enhance Ability, Fire
Shield, Flame Strike, Green-Flame Blade, Toll the Dead. Each aborts only when a source NPC
casts it with a limited (use-consuming) innate quota.

## Expected Behavior

When every candidate is a complete slot-consuming casting activity of the same kind (the
choice is made when casting), each candidate is a primary casting activity: all of them spend
the source casting quota, so whichever alternative the user picks consumes the same use.
Recurring or follow-up activities remain free. Failing closed remains correct for genuinely
ambiguous shapes.

## Regression Requirements

- Limited innate Flame Strike with two alternative `save` activities converts; both
  activities consume the item use and neither consumes a spell slot.
- The same structure under a different spell name and donor identity behaves identically.
- Controls: a single-activity spell, and a spell whose second activity is a free follow-up,
  keep their current behavior.

## Downstream Disposition

Dragoncoast Danger used a hash-bound converter-input donor shim (Radiant Scaling
`spellSlot: false` for selection only) and restored the converted item afterwards so both
alternatives spend the 1/day use.

## Triage And Generic Resolution

The eight-name scan was a candidate list, not proof of eight equivalent defects. The converter
now recognizes complete same-kind save choices with matching activation, targeting, duration,
save rules, and resource behavior but differing damage type/die/scaling. Complete utility choices
may differ by distinct applied effects. Labels and donor identities do not choose the rule.

This covers the measured Flame Strike, Destructive Wave, Fire Shield, and Toll the Dead shapes.
Each accepted choice spends the shared source Item use and no spell slot; free follow-ups remain
free. Mixed activity kinds, incomplete activities, and sequential weapon/damage operations are
not reclassified as casting alternatives merely because they occur on one spell. The other
candidate shapes require separate evidence before support can be broadened.

Regression cases use renamed spells and donor IDs, plus single-cast, free-follow-up, incomplete,
and mixed-shape controls in
[test_asset_and_compendium_fixes.py](../../tests/test_asset_and_compendium_fixes.py).
