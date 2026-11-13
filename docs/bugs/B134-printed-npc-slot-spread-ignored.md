# B134: A printed NPC slot spread is ignored in favor of a full-caster table

- Severity: High
- Status: Fixed in v1.17.1
- Observed release: R20Converter 1.17.0, commit eae5e7f (rule introduced by B030 in 1.1.0)
- Reported: 13 November 2026, Curse of Strahd 1.4.0 conversion intake D5 (*Sir Godfrey Gwilym*)
- Upstream copy filed by mistake: kakaroto/R20Converter#102
- Related: [B030](B030-npc-spellcasters-zero-slots.md)

## Reproduction

*Sir Godfrey Gwilym*'s Spellcasting trait reads "Sir Godfrey is a 16th-level spellcaster ... the
following paladin spells prepared: 1st level (4 slots) ... 2nd level (3 slots) ... 3rd level
(3 slots) ... 4th level (2 slots)". His sheet has every `lvl<N>_slots_total` at 0.

1.17.0 emits `attributes.spell.level: 16` and no overrides. dnd5e derives NPC slots from the
full-caster table, so he gets 4/3/3/3/2/1/1/1 instead of 4/3/3/2.

## Cause

Generic converter defect. B030 assumed that the sheet's `lvl<N>_slots_total` reproduces the printed
statblock, and otherwise left slot capacity to `spell.level`. A census of real exports contradicts
that assumption: Roll20 fills those totals from the full-caster table of the caster level.

| Export | NPC casters with sheet totals | Totals equal full-caster table | Totals differ from printed spread |
| --- | --: | --: | --: |
| Curse of Strahd 1.5.7 | 24 | 24 | 2 (*Flameskull* prints 3/2/1, sheet 4/3/2; *Donavich* prints 3, sheet 2) |
| Courts of the Shadow Fey 1.5.3 | 24 | 23 | 4 (*Aazael*, a paladin, prints 4/3/2, sheet 4/3/3/3/1; Sir Rujan; the Black Prince; Acolyte) |

Godfrey is the case with no totals at all. In every mismatch the printed spread is the published
statblock, and the sheet holds the generic table.

## Resolution

`Actor.getNPCPrintedSpellSlots` reads the standard statblock form `Nth level (K slot[s])` from NPC
traits named *Spellcasting*, excluding *Innate Spellcasting*. A level printed twice with different
counts is ambiguous: it warns and the sheet rule applies unchanged. When a printed spread exists:

- each level's override is the printed count, and every unprinted level is pinned to 0, so dnd5e's
  full-caster table cannot add slots;
- module exports start full; worlds keep the sheet's availability, starting full when the sheet
  row was full or empty and clamping partial pools to the printed capacity;
- a warning names the NPC when printed counts replace non-zero sheet totals.

Without a printed spread the B030 sheet-total rule and caster-level derivation are unchanged. The
caster level stays as printed for cantrip scaling, and characters are unaffected.

## Verification

`tests/test_dnd5e_schema_diff.py`: a renamed 16th-level paladin with no sheet totals (world and
module), a printed spread replacing full-caster sheet totals, a partially spent world pool, and
controls for innate traits, traits without a spread, conflicting spreads and characters. The 1.17.0
source fails all five fix cases. dnd5e 6.0.6 honors a numeric override of 0
(`spellcasting-model.mjs`).

Unmodified Curse of Strahd export, module output and Adventure: Sir Godfrey 4/3/3/2 with levels 5-9
pinned to 0, matching the pipeline's manual repair; Flameskull 3/2/1 and Donavich 3, matching their
statblocks. [B133](B133-npc-without-source-spellcasting-has-no-slots.md) records Strahd, whose source
has no spellcasting at all.
