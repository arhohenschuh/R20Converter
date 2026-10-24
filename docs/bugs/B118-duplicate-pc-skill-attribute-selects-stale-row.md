# B118: Duplicate PC skill attributes select the stale row

- Severity: Moderate
- Status: Open
- Observed release: R20Converter 1.16.1, commit cbb0d0e7a9665c43f780c26d3f31ef98f853454d
- Reported: 24 October 2026, Dragoncoast Danger played-world reconversion (`dcd/v130`)

## Reproduction

Roll20 PC Brandl Boggersham (Dragoncoast Danger R20Exporter 1.5.3) carries two `stealth_bonus`
attributes: `-NS5unZbKSsy9MGs9SO8 = 7` (with `stealth_type = 2`, expertise) and the later stale
`-NSWe2tEDXjGDgE6OOOU = 0`. The character-sheet PDF and the sheet's roll macro use +7. The
converted actor rolls Stealth at +1 (DEX +3 with an explicit `-3` check bonus to reach the stale
0) instead of +7.

The same character has five more duplicate gameplay pairs (`hitdieroll`, `other_tool`,
`other_languages`, `other_armor`, `other_weapon`) where the second row is empty.

## Cause

Attribute lookup returns the last row for a duplicated name. Roll20 renders and rolls from the
first (live) row. Stale second rows are left behind by sheet migrations.

## Expected Behavior

For duplicate attribute names, pick the row Roll20 itself uses (the first row; or prefer the
non-empty row consistent with `<skill>_type` / proficiency), and log every duplicate gameplay
conflict with both IDs.

## Regression Requirements

- Duplicate `stealth_bonus` 7/0 with `stealth_type = 2` converts to expertise with total +7.
- A different character/module with the same duplicate shape behaves identically.
- Control: a character with a single row is unchanged.
