# B123: Specific PC tool proficiencies are dropped

- Severity: Moderate
- Status: Open
- Observed release: R20Converter 1.16.2, commit 9c485df; source unchanged in 1.16.3 (39d9eaf)
- Reported: 25 October 2026, Dragoncoast Danger PC relevel (`dcd/relevel-001`), Foundry 14.369,
  dnd5e 6.0.6 Legacy

## Reproduction

Roll20 tool rows (`repeating_tool_*_toolname`) of the Dragoncoast Danger PCs and the converted
`system.tools`:

| PC | Roll20 tools | Converted `system.tools` |
| --- | --- | --- |
| Brandl Boggersham | Disguise Kit, Forgery Kit, Bagpipes, Lute | `disg`, `forg` |
| Medela Marigold Middleton | Woodcarver's Tools | none |
| Neverell Obarskyr | Dragonchess Set | none |

Every dropped tool has a dnd5e key (`bagpipes`, `lute`, `woodcarver`, `chess`), and a native relevel
through the same Beyond5e advancement grants it.

## Cause

`createTraitToolProficiencies` (`src/entities/actors.py`) recognises only category labels plus two
kits (`Artisan's Tools`, `Disguise Kit`, `Forgery Kit`, `Gaming Set`, `Herbalism Kit`,
`Musical Instrument`, `Navigator's Tools`, `Poisoner's Kit`, `Thieves' Tools`,
`Vehicle (Land or Water)`). Specific instruments, artisan's tools and gaming sets fall into
`custom`, which `createActorTools` (B037) only logs.

## Expected Behavior

Resolve tool names against the dnd5e tool registry (`CONFIG.DND5E.tools` base items and their
labels, for example *Woodcarver's Tools* -> `woodcarver`, *Dragonchess Set* -> `chess`,
*Bagpipes* -> `bagpipes`), case-insensitively and tolerant of the Roll20 "Set/Kit/Tools" suffixes.
Unresolvable names keep the current warning.

## Regression Requirements

- Bagpipes, Lute, Woodcarver's Tools and Dragonchess Set convert to their dnd5e keys.
- A different character/module with *Smith's Tools* and *Dice Set* converts to `smith` and `dice`.
- Control: Disguise Kit / Forgery Kit are unchanged; an unknown homebrew tool still warns.
