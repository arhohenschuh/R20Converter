# B124: Individual PC weapon proficiencies are dropped

- Severity: Minor
- Status: Fixed in v1.16.4
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

## Resolution In v1.16.4

OGL and Shaped weapon proficiency parsing now uses the shared base-item resolver before the
existing category/custom fallback, returning sorted, unique native keys. The base-item table
also includes `net`: the pinned 2014 SRD item is a `weapon` with `martialR` / `net`, although the
current static equipment registry defaults to 2024 and omits it.

The preceding published v1.16.3 CLI reproduces the loss. Native Foundry 14.369 / dnd5e 6.0.6
Legacy verifies newly acquired Hand Crossbow, Longsword, Rapier and Shortsword with no explicit
Item proficiency override. Light Crossbow remains proficient through the Simple category;
unlisted Longbow remains nonproficient. A separate Net test removes the Martial category,
proves proficiency from `net` alone, then removes `net` and requires a zero multiplier. The
acquired-weapon results survive client reload. Unknown homebrew names remain custom text.

Focused evidence is retained under
`D:/Automation_Local/Work/Tooling/r20converter/v1164-b122-b124/Reports/`.
