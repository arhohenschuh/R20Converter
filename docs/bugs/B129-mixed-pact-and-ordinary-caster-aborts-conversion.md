# B129: A mixed pact and ordinary caster PC aborts the whole conversion

- Severity: High
- Status: Fixed in v1.17.1
- Observed release: R20Converter 1.17.0, commit eae5e7f (behavior introduced with B119 in 1.16.2)
- Reported: 13 November 2026, *Eberron - Rising from the Last War* campaign export
  (`Eberron - Rising from the Last War_Campaign-1.5.7.zip`, SHA-256 `4431746E…4E7`), R20Exporter 1.5.7

## Reproduction

Convert any campaign with an OGL-sheet PC that multiclasses a pact class with an ordinary
spellcasting class. The conversion stops at that actor:

```text
File "src/entities/actors.py", line 1843, in applyPCPactMagic
    raise ValueError("Cannot split mixed pact and ordinary spellcasting from one source slot row")
```

In the reported export the actor is a Bard 4 / Warlock 4 (College of Lore / The Fiend). Every
document already created is discarded; nothing is written.

| Source field | Value |
| --- | --- |
| `class`, `base_level` | Bard, 4 |
| `multiclass1`, `multiclass1_lvl` | Warlock, 4 |
| `lvl1_slots_total` | 4 |
| `lvl2_slots_total` | 5 |
| `lvl<N>_slots_expended` (available slots) | absent at every level, read as 0 |
| spell rows `spellclass` / `spellsource` | empty on all 13 leveled spells |

## Triage

Generic converter defect; no module, export or content correction is needed. B119 deliberately
rejected every mixed pact/ordinary PC because the OGL sheet keeps one slot row per level and the
spell rows carry no class. Re-examined:

- **The row is a sum, and it is consistent with the classes.** dnd5e (5.3.3 and 6.0.6,
  `SlotSpellcasting.computeProgression`, `CONFIG.DND5E.spellcasting`) gives Bard 4 ordinary slots
  4/3 and Warlock 4 two 2nd-level pact slots. 4 and 3 + 2 = 5 are exactly the sheet totals.
- **Capacity is derived, not read.** For characters the converter writes no override; dnd5e
  derives both pools' maxima from the emitted classes. Only the available counts come from the
  sheet, and they only collide at the pact slot level.
- **Spell attribution is not needed.** Neither the `spell` nor the `pact` spellcasting method sets
  `exclusive.spells` or `exclusive.slots`, so the cast dialog offers both pools to any slot-cast
  spell (`ActivityUsageDialog`, 6.0.6). Ordinary spells can stay `method: "spell"`.
- **Most splits are exact.** Levels without pact slots belong to the ordinary pool. At the pact
  level the split is unique when the row is full (both pools full), empty (both empty), or when
  the ordinary pool has no slot of that level. Module exports use class capacities.
- **The remaining partial case has a conservative rule.** Filling the pact pool first preserves
  the available total now and never credits more than the true state after a short rest, when
  pact slots recover. It may under-credit an ordinary slot until the next long rest.

Aborting the whole conversion for one actor is the user-visible failure; the boundary B119 chose
is broader than the input requires.

## Expected Behavior

- A mixed pact/ordinary PC converts. Ordinary capacity follows dnd5e's multiclass progression
  (full 1, half 1/2 rounded up, third 1/3, artificer 1/2 rounded up; a single non-full class
  rounds up); pact capacity follows the pact table.
- Available slots at non-pact levels go to `spells.spell<N>.value`. At the pact level the split is
  exact where determinable and pact-first otherwise, with a warning naming the actor.
- Sheet totals that disagree with the derived capacities produce a warning, not an abort.
- Ordinary spells keep `method: "spell"`; explicit at-will grants still become `atwill`.
- Single-class pact casters and non-pact casters are unchanged.

## Regression Requirements

- Renamed Bard/Warlock fixture: empty, full and partial rows; world and module exports.
- Non-overlapping levels (pact level above or below the ordinary maximum); half, third and
  artificer partners; a totals mismatch control.
- Existing single-pact and non-pact controls unchanged.
- Real export: the reported campaign converts, and the actor carries the derived split.

## Resolution

`dnd5e.ordinaryCasterLevel` mirrors `SlotSpellcasting.computeProgression` with the configured
`full`/`half`/`third`/`artificer` divisors, and `dnd5e.pactSlots` mirrors the pact table. When a
PC has both a pact class and ordinary slots, `Actor.splitMixedSlotRows` writes each level's
available count to the ordinary pool, except at the pact slot level, where the exact split is used
when it is unique and the pact pool is filled first otherwise. Module exports use both class
capacities. A partial split and any sheet total that differs from the class-derived total are
logged with the actor name. Ordinary spells keep `method: "spell"`; source at-will grants still
become `atwill`. Progressions other than pact, none and the four slot progressions still fail
explicitly.

Regression coverage (`tests/test_dnd5e_schema_diff.py`): renamed Bard/Warlock-shaped classes with
empty, full and two partial rows in world mode and a module export; ordinary methods and an
at-will grant; a pact level above the ordinary maximum; half, third and artificer partners; a
totals mismatch; unknown progressions; and the dnd5e caster-level and pact tables. Exported HEAD
fails all 29 new tests.

Real export, converted with pinned dnd5e 6.0.6 and Beyond5e 1.6.72 (replace mode): the campaign
converts with 165 actors and 42 scenes once B130 is also fixed. The actor is Bard 4 (`full`) /
Warlock 4 (`pact`); its slot values are 0 because the sheet records no available slots, no
totals warning is raised, and *Disguise Self* is `atwill` through *Mask of Many Faces*.
