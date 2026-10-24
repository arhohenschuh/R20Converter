# B119: Pact-magic PC spells are written as ordinary spellcasting and the pact slot reads 0

- Severity: High
- Status: Open
- Observed release: R20Converter 1.16.1, commit cbb0d0e7a9665c43f780c26d3f31ef98f853454d
- Reported: 24 October 2026, Dragoncoast Danger played-world reconversion (`dcd/v130`)

## Reproduction

Convert a world that contains a single-class Warlock PC with the OGL sheet. Dragoncoast Danger
has two: Gerbo "Neunmalklug" Ningel and Pesch Serkel, each Warlock 4. Their Roll20 sheets hold
`lvl2_slots_total = 2` and `lvl2_slots_expended = 2`. On the OGL sheet, `expended` is the number
of slots still available.

| Field in the converted actor (dnd5e 5.3.3 schema, before migration) | Value |
| --- | --- |
| Class item `system.spellcasting.progression` | `pact` (correct) |
| Every spell `system.method` | `spell`, except Gerbo's *Command* (`innate`, correct) |
| `system.spells.pact.value` | `0` |
| `system.spells.spell2.value` | `2` |

Effect in Foundry 14.369 / dnd5e 6.0.6: the sheet does not list the spells under Pact Magic, and
the pact slot shows 0/2. Neither warlock can cast a leveled spell from a pact slot until a short
rest. The previous 1.2.2 world, re-levelled through the advancement UI, had every warlock spell as
`pact`.

## Cause

- The spell method is chosen as for a prepared or known caster and ignores the owning class's
  `pact` progression.
- The current slot count is read per spell level (`lvl<N>_slots_expended`) and written to
  `spells.spell<N>.value`. For a pact caster the same number belongs in `spells.pact.value`.
- A spell that an invocation grants at will is not distinguished. Pesch's *Disguise Self* comes
  from *Mask of Many Faces*, so it is `atwill` by rule; the converter writes `spell`.

## Expected Behavior

- If an actor's only casting class has `pact` progression, every class spell gets `method: "pact"`.
- Spells the source marks as racial, feat or invocation grants keep `innate` or `atwill`.
- The available-slot count at the pact slot level goes to `spells.pact.value`, and that ordinary
  `spell<N>.value` stays 0.
- Multiclass actors that combine pact and ordinary slots need an explicit rule. Roll20 OGL keeps one
  slot row per level, so decide which pool receives the count and test it.

## Regression Requirements

- A single-class Warlock: all class spells are `pact`, the pact slot equals the Roll20 available
  count, and there are no ordinary slots.
- A Warlock with a feat- or invocation-granted spell: that spell keeps `innate`/`atwill`.
- A Warlock/Sorcerer (or Warlock/Paladin) multiclass fixture covering the documented split rule.
- Controls: Bard, Cleric and Wizard PCs are unchanged, with `method: "spell"` and ordinary slot
  values.
- Use a renamed fixture with different actor identities; the fix must not key on names.

## Downstream Disposition

Dragoncoast Danger repairs this after conversion as phase 6: C5 sets 26 spells to `pact` and one
to `atwill`, and C6 moves 2 slots from `spell2` to `pact` for each warlock. The record is
`Reports/phase6-apply-002.json`.
