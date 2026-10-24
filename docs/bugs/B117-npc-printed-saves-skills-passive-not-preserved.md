# B117: OGL NPC printed saves, skills and passive Perception are not preserved

- Severity: Moderate
- Status: Open
- Observed release: R20Converter 1.16.1, commit cbb0d0e7a9665c43f780c26d3f31ef98f853454d
- Reported: 24 October 2026, Dragoncoast Danger played-world reconversion (`dcd/v130`)

## Reproduction

Same conversion as B116. Compare each OGL NPC's printed `npc_<ability>_save` (with
`npc_saving_flag`), printed skills (`npc_<skill>` with `npc_<skill>_flag`), and the printed
`passive Perception N` in `npc_senses` with runtime dnd5e 6.0.6 totals:

| NPC | Printed | Converted |
| --- | --- | --- |
| Fredo "Fredie Flinkfinger" | Dex save +4, Cha save +3, passive Perception 12 | +3, +2, 9 |
| "Der Grinsende" Galvyn | Dex save +7 | +6 |
| Orin Eisenholz | Int save +6, Wis save +4 | +5, +3 |
| Shegren | Acrobatics +4, Deception +2, Perception +2, Stealth +5 | 3.5, 1.5, 1.5, 4.5 |
| Sara / Shaena Zehnpfennig | passive Perception 10 / 11 | 12 / 13 |

## Cause

- Saves: `createActorAbility` only sets `proficient = save >= mod + prof`. Any printed save that is
  neither the modifier nor modifier + proficiency (sidekick and custom NPCs) is reduced to one of
  those two values; the difference is never carried as a save bonus.
- Skills: the proficiency multiplier is derived from `printed - mod` divided by the sheet's
  proficiency bonus. Shegren's sheet has `npc_pb = 0` with CR 5, so the derived multiplier
  becomes 0.5 and every total gains a half point (3.5 instead of 4).
- Passive Perception: the printed senses value is not compared with the derived passive score.

## Expected Behavior

Printed NPC scalars are authoritative. When the derived total differs, emit the smallest native
representation that reproduces the printed value (proficiency flag plus explicit save/check/
passive bonus). Never emit fractional proficiency.

## Regression Requirements

- Fredo-style flat saves (+4 Dex with mod +3, PB +2) reproduce exactly.
- An NPC with `npc_pb = 0` and printed skills produces integer totals equal to the printed values.
- A printed passive Perception that differs from 10 + Perception is preserved.
- Controls: standard NPCs whose printed values equal the derivation are unchanged.

## Downstream Disposition

Dragoncoast Danger repairs 5 saves, 4 skills, and 3 passive scores post-conversion (rules R-SAVE,
R-SKL, R-PAS).
