# B037: Character tool proficiencies emitted as legacy `traits.toolProf` — 5.x uses `system.tools`

- **Status**: Fixed in 1.0.2 (F037)
- **Severity**: Minor (works today via a dnd5e migration shim; violates ADR-008's zero-migration invariant)
- **Found**: 2026-08-03 audit
- **Component**: `src/entities/actors.py:1522-1555`, `1567-1572` (`createActorTraits`)

## Defect

Characters emit `traits.toolProf = {value: [...], custom: "..."}`. dnd5e moved
tool proficiencies out of traits and into a `system.tools` mapping of
`RollConfigField`s (`module/data/actor/templates/creature.mjs:57`), keyed by tool
id with `{value, ability, bonuses}`. The old key survives only through the
`migrateTraitData` shim (`creature.mjs:166-174`), which filters entries against
`CONFIG.DND5E.toolProficiencies`/`tools` at load time.

Consequences:

- The stored document is non-native; the data works only for as long as dnd5e
  keeps the shim, which is precisely the dependency ADR-008 was written to
  remove (compare B004, B019, B021).
- The converter's key vocabulary (`art`, `disg`, `forg`, …) is the legacy
  *category* list; several of the shim's accepted per-tool ids (e.g.
  `alchemist`, `thieves'`) are never produced, so specific tools land in
  `custom` and get no roll support.

`traits.armorProf` and `traits.weaponProf` are still native in 5.x
(`character.mjs:112-118`) and are fine.

## Suggested fix

Emit `system.tools = {<toolId>: {value: 1, ability: "int", bonuses: {check: ""}}}`
for recognised tools (mapping Roll20 names → `CONFIG.DND5E.tools` ids), keep the
unrecognised remainder in `traits.toolProf.custom` only if the shim keeps
honouring it — otherwise surface it in the biography like other unrepresentable
data.
