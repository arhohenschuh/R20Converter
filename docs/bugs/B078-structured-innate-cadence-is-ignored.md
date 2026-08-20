# B078 - Structured and trait-only innate cadence is ignored

**Severity:** High
**Status:** Fixed in v1.15.0
**Found:** 2026-08-20 during Tomb of Annihilation v1.14.0 qualification
**Component:** `src/entities/actors.py` (`addSpells`)
**Related:** B036, B062, B064

## Defect

`addSpells()` reads innate cadence only from each repeating spell row's `innate` or
`spell_innate` field. Roll20 OGL NPCs can instead carry the authoritative cadence in
`kingdom_drop_data.data-Spells`, or only in an Innate Spellcasting trait. Those spells are emitted
as ordinary `method: spell` Items with no use pool even though the immutable Actor data says
at-will or N/day.

## Evidence

Fresh Tomb of Annihilation v1.14.0 output required nine source-backed corrections:

- four structured `data-Spells` cases (Fenthaza: Darkness, Fear, Suggestion; Kobold Scale
  Sorcerer: Levitate);
- five unique trait fallbacks (Sekelok: Suggestion and Animal Friendship; King of Feathers:
  Misty Step; King Groak: Scorching Ray; Laskilar: Dimension Door).

The source contracts are two 1/day, three 2/day, two 3/day, and two at-will spells. All nine
arrived as ordinary slot spells with an empty root pool.

## Fix contract

- Parse `kingdom_drop_data.data-Spells` when present and treat its cadence buckets as the
  cardinality authority.
- Reconcile structured entries to emitted Items by unambiguous normalized Actor, spell name, and
  level.
- Use exact Innate Spellcasting trait clauses only as a fallback when they identify one emitted
  spell unambiguously.
- Set method, preparation, pool/recovery, and primary use consumption as one contract.
- Reject contradictory or ambiguous cadence instead of guessing.

## Regression coverage required

Cover structured at-will/N-day data, duplicate repeating rows, trait-only cadence, ambiguous
same-name controls, and verification that ordinary prepared spells remain slot-based.

## Resolution

`Actor.inferInnateCadence()` reconciles normalized spell name and level against structured
`data-Spells`, exact trait buckets, innate-at-will clauses, and named next-dawn traits. Duplicate or
contradictory matches abort. `addSpells()` uses inference only when the repeating row has no explicit
cadence, then follows its existing native method/pool/activity path. Unit tests and the immutable
ToA verifier cover all nine measured rows.