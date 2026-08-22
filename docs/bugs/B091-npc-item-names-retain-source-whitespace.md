# B091 - NPC Item names retain source whitespace

**Severity:** Minor
**Status:** Fixed in v1.15.3
**Found:** 2026-08-21 during *The Sunless Citadel* v1.15.2 reconversion
**Component:** `src/entities/actors.py` (`addTraits`, `addNPCAction`, `nameOrPlaceholder`)
**Related:** B047, B075, B090

## Defect

NPC repeating-section names are emitted without trimming leading or trailing whitespace. Roll20
can store a line break before an action or trait name; R20Converter preserves that control
character in the Foundry Item name and performs any same-name compendium lookup against the
untrimmed value.

The immutable *Sunless Citadel* source contains exactly three affected repeating names:

- Guthash: `"\nKeen Smell."`;
- Diseased Giant Rat: `"\nKeen Smell."`;
- Kobold Elite: `"\nDagger (Ranged)"`.

R20Converter 1.15.2 emitted all three names with the leading newline. The release pipeline later
canonicalized them to `Keen Smell.` and `Dagger (Ranged)`. The measured examples remained usable,
so this is minor, but exact-name matching, search, sorting, and presentation are all affected. A
whitespace-only source name would also bypass `nameOrPlaceholder()`'s empty-name handling.

## Evidence

- Immutable source:
  `TotYP_The Sunless Citadel_R20Export-1.0.0.zip`, 68,153,994 bytes,
  SHA-256 `BA07133AC97DF6A7AE3E3E71D10C866E4A8E4055B25D8DC0D85FA1D47F8E5041`.
- Source Actor IDs: `-KcsxPZfrtLOjhgHo8lm`, `-Kd2RhdxXilfPmPLRPrK`, and
  `-KctMCRk9XLQr32k_8Fe`.
- Semantic differential:
  `reports/baseline-vs-v1.15.2-semantics.json`, SHA-256
  `EBE91ECC7391CB4F4205CACA1F6C10E89915CCB02E2A9BF69C5ED14B52A55154`.

Evidence root:
`D:\Automation_Local\Two_Channel\tftyp-the-sunless-citadel\release\1.2.1-reconversion-001`.

## Required handling

- Normalize leading and trailing whitespace at the NPC Item-name boundary before placeholder
  selection, compendium lookup, activity-ID derivation, and document creation.
- Preserve meaningful internal whitespace and punctuation.
- Treat a whitespace-only source name as empty so the existing descriptive placeholder is used.

## Regression coverage required

Convert NPC trait and action names with leading/trailing newlines and spaces. Assert clean Item
names, lookup using the normalized name, stable activity IDs derived from that name, and placeholder
handling for a whitespace-only value.

## Resolution

`nameOrPlaceholder()` now trims outer whitespace before testing for an empty name. NPC actions
normalize before their preliminary type lookup, while all Item factory paths receive the same
normalized name through the existing boundary. Focused regressions cover lookup/creation and the
whitespace-only placeholder case.