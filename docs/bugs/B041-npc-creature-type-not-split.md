# B041: NPC creature type stores "humanoid (goblinoid)" whole instead of value + subtype

- **Status**: Open
- **Severity**: Minor (cosmetic/filtering; no validation failure)
- **Found**: 2026-08-03 audit
- **Component**: `src/entities/actors.py:626-636` (`getNPCType`), `1121` (`createActorDetails`)

## Defect

For an OGL-sheet NPC, `npc_type` reads like `"Small humanoid (goblinoid),
neutral evil"`. `getNPCType()` returns the middle chunk unsplit, and
`details.type` is emitted as:

```python
{"value": "humanoid (goblinoid)", "subtype": "", "swarm": "", "custom": ""}
```

`CreatureTypeField.value` is a blank-allowed `StringField` without choices
(`module/data/shared/creature-type-field.mjs:9`), so the junk value is *stored*,
but every consumer looks it up in `CONFIG.DND5E.creatureTypes` — the label
resolves to undefined, type-based filtering/automation (e.g. ranger favored
enemy, compendium browser filters) does not match "humanoid", and the sheet
falls back to showing raw text. Also unhandled: `"swarm of Tiny beasts"`, which
should populate `swarm: "tiny"`.

## Suggested fix

Parse the parenthetical into `subtype` and validate the head word against the
dnd5e creature-type keys (`aberration`…`undead`), falling back to
`custom` for anything unrecognised; detect the `"swarm of <Size> <type>s"`
pattern and fill `swarm` with the size key. The size word is already parsed off
correctly for `traits.size`.
