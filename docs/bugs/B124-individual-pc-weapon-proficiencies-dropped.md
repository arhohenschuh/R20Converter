# B124: Individual PC weapon proficiencies are dropped

- Severity: Minor
- Status: Open
- Observed release: R20Converter 1.16.2, commit 9c485df; source unchanged in 1.16.3 (39d9eaf)
- Reported: 25 October 2026, Dragoncoast Danger PC relevel (`dcd/relevel-001`), Foundry 14.369,
  dnd5e 6.0.6 Legacy

## Reproduction

Roll20 PC Brandl Boggersham (Bard) lists weapon proficiencies `Simple weapons`, `Hand Crossbow`,
`Longsword`, `Rapier`, `Shortsword` (`repeating_proficiencies`, `prof_type = WEAPON`). The converted
actor has `traits.weaponProf.value = ["sim"]`; a native relevel has
`handcrossbow, longsword, rapier, shortsword, sim`.

Present-day attacks are unaffected because each converted weapon item carries its own
`proficient` flag (Rapier still hits at +5). The loss shows when the PC picks up a new weapon of a
listed kind: dnd5e derives that weapon's proficiency from `traits.weaponProf`, so it rolls without
the proficiency bonus.

## Cause

`createTraitWeaponProficiencies` (`src/entities/actors.py`) recognises only `Simple Weapons` and
`Martial Weapons`. Individual weapon names fall through to `custom` (free text, which dnd5e does not
use for proficiency).

## Expected Behavior

Map individual weapon names through the existing base-item table (`dnd5e.weaponBaseItem`, which
already resolves `handcrossbow`, `longsword`, `rapier`, `shortsword`, ...) into
`traits.weaponProf.value`; keep category matching case-insensitive (`Simple weapons`); put
unresolvable names into `custom`.

## Regression Requirements

- `Simple weapons, Hand Crossbow, Longsword, Rapier, Shortsword` converts to
  `["handcrossbow", "longsword", "rapier", "shortsword", "sim"]`.
- A different character/module with `Martial Weapons, Net` converts to `["mar", "net"]`.
- Control: `Simple Weapons` alone is unchanged; an unknown homebrew weapon goes to `custom`.
