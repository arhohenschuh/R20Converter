# B133: An NPC whose Roll20 sheet has no spellcasting converts without slots

- Severity: Info
- Status: Not a converter defect
- Observed release: R20Converter 1.17.0, commit eae5e7f
- Reported: 13 November 2026, Curse of Strahd 1.4.0 conversion intake D4 (*Strahd von Zarovich*)
- Upstream copy filed by mistake: kakaroto/R20Converter#101

## Report

The converted NPC has `attributes.spellcasting: ""`, `attributes.spell.level: 0` and no slots,
although the published statblock makes him a 9th-level Intelligence caster with 4/3/3/3/1 slots.

## Source Evidence

The NPC's own Roll20 sheet in `Curse of Strahd-1.5.7.zip` (SHA-256 `A0319692…ABCE`) has
spellcasting switched off and carries none of that information:

| Source attribute | Value |
| --- | --- |
| `npcspellcastingflag` | `0` |
| `spellcasting_ability` | `0*` |
| `caster_level`, `spell_save_dc`, `spell_attack_bonus` | `0` |
| `lvl1_slots_total` … `lvl9_slots_total` | `0` |
| NPC traits | Shapechanger, Legendary Resistance, Misty Escape, Regeneration, Spider Climb, Vampire Weaknesses; **no Spellcasting trait** |

His 17 spell rows exist, and the converter emits them. Nothing in the source states a caster level,
ability or slot spread. Supplying one would invent statblock data.

## Disposition

The converter faithfully reproduces the source sheet. The values belong to a campaign-specific
post-conversion repair, as the Curse of Strahd pipeline already does. Statblocks that *print* their
slot spread in a Spellcasting trait are converted from it; see [B134](B134-printed-npc-slot-spread-ignored.md).
