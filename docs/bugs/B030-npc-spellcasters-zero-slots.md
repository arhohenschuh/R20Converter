# B030: NPC spellcasters arrive with zero spell slots

- **Status**: Fixed in 1.1.0 (F030)
- **Severity**: Major (every leveled NPC caster is unusable as printed)
- **Found**: 2026-08-03 audit
- **Component**: `src/entities/actors.py:1127` (`details.spellLevel`), `1593-1600` (`createActorSpells`), `1028-1029` (`attributes.spelldc`/`spellLevel`)

## Defect

Three cooperating problems:

1. `createActorSpells` emits `spells.spellN = {value, max, override: None}`.
   The 5.x creature schema (`module/data/actor/templates/creature.mjs:66-74`)
   declares only `{value, override}` — **`max` is derived**, so the emitted max is
   dropped and `override` is never set.
2. For NPCs, slot maxima are derived from the caster level in
   `attributes.spell.level`. The converter emits `("spellLevel", 0)` into
   `details` (line 1127) — a legacy key that dnd5e's shim
   (`module/data/actor/npc.mjs:279-286`) migrates via
   `attributes.spell.level ??= details.spellLevel`, i.e. **caster level 0**.
3. Worse, emitting the hardcoded `0` actively defeats dnd5e's own safety net:
   `npc.mjs:384-385` falls back to `max(cr, 1)` only when `spell.level` is *not*
   numeric — and `0` is numeric.

Net result: progression derives zero slots of every level. The NPC's leveled
spells are all present but uncastable as printed. (`attributes.spelldc` and
`attributes.spellLevel` are also emitted; neither exists in the 5.x schema.)

## Suggested fix

- Stop emitting `details.spellLevel` and `attributes.spelldc`/`spellLevel`.
- Parse the caster level from the NPC spellcasting trait text
  ("is a 9th-level spellcaster") and emit it natively as
  `attributes.spell.level`; when unparseable, emit nothing and let the
  `max(cr, 1)` fallback work.
- Alternatively (or additionally, for exactness) set `spells.spellN.override`
  to the slot counts read off the sheet (`lvlN_slots_total`).

## Correction found while fixing (2026-08-03)

Point 3 above is **wrong**, and the suggested fix inherited the error.

`NPCData.defineSchema` declares the field as

```js
spell: new SchemaField({
  level: new NumberField({ required: true, nullable: false, integer: true, min: 0, initial: 0 })
})
```

`nullable: false, initial: 0` means `spell.level` is *always* a number. A
non-numeric value cannot occur, so a `max(cr, 1)` fallback guarded on
"not numeric" can never fire in 5.3.3. There is no safety net to defeat, and
"emit nothing and let the fallback work" would have produced caster level 0 —
the exact bug being fixed.

What the source actually does (`Actor5e.prepareSpellcasting`):

```js
if ( this.system.isNPC && ("spell" in (this.system.attributes ?? {})) ) {
  const level = Object.values(progression).find(_ => _);
  if ( level ) this.system.attributes.spell.level = level;
  else if ( this.system.attributes.spell.level > 0 ) { … progression.spell = … }
}
```

Slots follow from `spell.level` and nothing else, and the sheet reads
`spells.override ?? spells.max ?? 0`. So the fix has to supply a real value, not
withhold one.

## Fix as shipped (F030)

- `spells.spellN` emits `{value, override}` only; `spell0` is dropped, since
  `CreatureTemplate._spellLevels` filters level 0 out.
- NPCs get `override` from the sheet's `lvlN_slots_total`, which reproduces the
  printed statblock exactly instead of inferring it.
- Characters get `override: None` — their class progression is emitted and
  authoritative, and pinning an override would freeze slots against level-ups.
- `attributes.spell.level` is emitted for NPCs, parsed from the Spellcasting
  trait ("is a 9th-level spellcaster").
- `details.spellLevel`, `attributes.spelldc` and `attributes.spellLevel` are no
  longer emitted.

`lvlN_slots_expended` holds the slots *remaining*, not the slots spent — the
sheet labels that field "SLOTS REMAINING" (`slots_remaining-u` in
`translations.py`). It maps onto `value` unchanged; the original code was right
about that and the mapping was deliberately left alone.

## Note on PCs

Characters get slots from their class items' spellcasting progression, so they
are unaffected as long as the class conversion is right. `pact` is emitted with
`{value: 0, override: None}`, which zeroes a warlock's *current* pact slots but
keeps the max derivable.
