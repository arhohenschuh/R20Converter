# B068 - Spell resource gate blocks non-spell donors

**Severity:** High
**Status:** Fixed in v1.14.0
**Found:** 2026-08-20 during frozen LMoP qualification

## Defect

The v1.13.0 G29 validator ran on every Item type. Beyond5e 1.1.11's Torch has a known non-spell
`itemUses` target without a usable root pool, so matching that donor aborted the whole LMoP
conversion. G29 and the v1.13.0 roadmap slice govern Actor spell capacity, availability, and
consumption; they do not transfer all custom-compendium item QA into R20Converter.

## Fix contract

- Fail closed for unsatisfied spell self-use pools and double spell/item consumption.
- Leave non-spell donor activity contracts unchanged and donor-owned.
- Continue to clone/internalize the donor document only when the module otherwise uses it.

## Regression coverage

`tests/test_asset_and_compendium_fixes.py` retains all spell rejection controls and proves a
Torch-like non-spell donor remains loadable.