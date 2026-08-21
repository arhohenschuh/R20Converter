# B082 - Unique slot-consuming donor primary is not selected

**Severity:** High
**Status:** Fixed in v1.15.2
**Found:** 2026-08-20 during Eberron Setting v1.15.1 candidate conversion
**Component:** `src/entities/items.py` (`_mergeSpellConsumption`)
**Related:** B029, B062, B064, B077

## Defect

The B077 selector prefers a unique same-type activity, the canonical `dnd5eactivity000`, or a sole
donor activity. It rejects a same-type pair even when existing donor consumption distinguishes one
initial cast from one free follow-up.

The pinned Eyebite donor contains two save activities:

- `saveEyebiteIIIII`: initial cast, `consumption.spellSlot: true`.
- `saveEyebiteIIclo`: named `Concentration Action`, `consumption.spellSlot: false`.

Kalaraq Quori casts Eyebite 3/day. The source therefore contributes one item-use consumer, but
v1.15.0 cannot select a primary and aborts conversion before package assembly.

## Fix contract

- Keep the canonical activity ID as the first preference.
- Otherwise select the sole activity whose existing donor consumption has `spellSlot: true`.
- Otherwise select a sole remaining activity.
- Preserve a free follow-up's empty targets and `spellSlot: false` state.
- Continue failing closed when multiple activities consume slots or no unique primary exists.

## Regression coverage required

An Eyebite-shaped initial-save plus concentration-follow-up donor must put exactly one item-use
consumer on the initial activity. A paired donor with two slot-consuming saves must still raise the
primary-selection error.

## Resolution

Primary selection now applies the same ordered rules to type-matched and fallback candidates:
canonical ID, unique slot consumer, then sole activity. Positive and ambiguous-donor controls pass.