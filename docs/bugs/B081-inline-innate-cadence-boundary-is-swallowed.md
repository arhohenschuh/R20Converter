# B081 - Inline innate cadence boundary is swallowed

**Severity:** High
**Status:** Fixed in v1.15.2
**Found:** 2026-08-20 during Eberron Setting v1.15.0 conversion
**Component:** `src/entities/actors.py` (NPC innate cadence inference)
**Related:** B062, B064, B077, B078

## Defect

The trait cadence parser captured from a line's first cadence marker through its newline. Roll20
can store multiple cadence lists on one line, so a later marker became part of the preceding spell
name list. Any remaining names after that marker inherited the wrong cadence.

The immutable Hashalaq Quori source contains:

`At will: charm person 3/day each: detect thoughts, disguise self, suggestion`

The explicit spell rows correctly store `Charm Person` as at will and `Disguise Self` and
`Suggestion` as 3/day. Version 1.15.0 inferred the latter names as at will and aborted conversion
on the explicit-versus-inferred contradiction.

## Fix contract

- Segment each cadence-list line at every `At will:` or `N/day [each]:` marker.
- Assign only the text between adjacent markers to that cadence.
- Continue requiring the first marker to begin the line, apart from whitespace, so prose containing
  an incidental cadence phrase is not interpreted as a list.
- Preserve multiline lists, structured `data-Spells`, named next-dawn traits, ambiguity rejection,
  and genuine contradiction rejection.

## Regression coverage required

An inline `At will` followed by `3/day each` must produce distinct cadence buckets for every named
spell. Existing focused cadence tests must remain green.

## Resolution

Trait descriptions are split into lines, cadence markers are enumerated within each qualifying
line, and each marker receives only its bounded slice. The Hashalaq-shaped regression fails against
v1.15.0 and passes with the fix; the full cadence class remains green.