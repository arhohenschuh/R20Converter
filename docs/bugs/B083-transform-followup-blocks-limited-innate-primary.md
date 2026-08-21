# B083 - Transform follow-up blocks limited innate primary selection

**Severity:** High
**Status:** Fixed in v1.15.2
**Found:** 2026-08-20 during Eberron Setting v1.15.1 candidate conversion
**Component:** `src/entities/items.py` (`_mergeSpellConsumption`)
**Related:** B029, B062, B064, B077, B082

## Defect

The Polymorph donor has a save activity for the cast and a transform activity for the resulting
form choice. Both carry `consumption.spellSlot: true`, neither uses the canonical activity ID, and
the Roll20 source row is utility-shaped. The B082 selector therefore has no type match and no
unique slot consumer, so it aborts instead of assigning Pixie's 1/day use.

## Fix contract

- Keep canonical and unique slot-consumer selection ahead of this rule.
- When several candidates consume slots and exactly one is not a transform activity, select that
  non-transform activity as the cast primary.
- Copy exactly one item-use consumer to the cast and make the transform follow-up non-consuming.
- Do not select among two or more non-transform slot consumers.
- Name the affected spell in any remaining primary-selection error.

## Regression coverage required

A utility source merged into a save-plus-transform donor must charge the save exactly once and keep
the transform free. The existing two-save ambiguity control must continue to raise.

## Resolution

After canonical and unique-slot checks, primary selection now accepts the sole non-transform slot
consumer. Polymorph's save becomes primary, its transform remains a free follow-up, and unrelated
multi-save ambiguity still fails closed.