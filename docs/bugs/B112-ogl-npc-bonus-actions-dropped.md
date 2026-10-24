# B112: OGL NPC bonus actions are never converted

- Severity: High
- Status: Open
- Observed release: R20Converter 1.16.1, commit cbb0d0e7a9665c43f780c26d3f31ef98f853454d
- Reported: 24 October 2026, Dragoncoast Danger played-world reconversion (`dcd/v130`)

## Reproduction

Convert any Roll20 OGL 5e campaign whose NPC sheets use the sheet's Bonus Actions section
(`npcbonusactionsflag = 1`, rows `repeating_npcbonusaction_<row>_name/_desc`). Measured on the
Dragoncoast Danger R20Exporter 1.5.3 archive, SHA-256
`0397FED99A837241EF9805A2C345B0EE8E33AE98129ECAEC01BC45762D4639D3`, with world output,
dnd5e 5.3.3 and Beyond5e 1.6.60:

| Source NPC | Bonus-action rows |
| --- | --- |
| Fredo "Fredie Flinkfinger" | Helpful, Dash, Disengage, Hide, Fast Hands |
| Urstar | Second Wind |
| "Der Grinsende" Galvyn | Cunning Action |
| Jelvard | Displacement (Recharge 5–6) |
| Rolan "Der Nachtwisper" | Cunning Action |
| Shaena Zehnpfennig | Unerring Tracker |
| Kommandantin Elicia Montoya | Second Wind (Recharges after a Short or Long Rest) |
| Bard | Taunt (2/Day) |
| Sheela Peryroyl | Healing Light (2/Day) |

All 13 rows across 9 NPCs are absent from the converted actors. The conversion log reports
nothing; exit code 0.

## Cause

`Actor.addActions` (OGL branch) reads `npcaction` (`ACTION`) and `npcaction-l` (`LEGENDARY`);
`Actor.addTraits` reads `npctrait` and `npcreaction`. No code path reads
`repeating_npcbonusaction`, so the section is silently discarded. The shaped-sheet branch is
unaffected by this report.

## Expected Behavior

Each `npcbonusaction` row becomes an NPC feature with a bonus-action activation, carrying the
same name/description/attack/save/damage handling that `addNPCAction` applies to ordinary
actions (equivalently: call `addNPCAction(items, action, ItemActivation.BONUS)` for every
non-empty row). Usage limits printed in the name ("(2/Day)", "(Recharge 5–6)", "Recharges
after a Short or Long Rest") follow the same rules as ordinary NPC actions.

## Regression Requirements

- An OGL NPC with one bonus-action row and one ordinary action converts both; the bonus action
  has activation type `bonus`.
- An attack-flagged bonus action keeps its to-hit and damage like an ordinary NPC action.
- A different module/actor identity with the same structure behaves identically.
- Control: an NPC without the section produces no extra items.

## Downstream Disposition

Dragoncoast Danger 1.3.0-rc.1 repairs the 13 rows post-conversion, outside the converter,
from the immutable source rows.
