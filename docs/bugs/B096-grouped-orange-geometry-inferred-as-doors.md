# B096 - Grouped orange geometry is inferred as doors

**Severity:** High
**Status:** Fixed in v1.15.8
**Found:** 2026-08-25 during official-versus-converted *Shattered Obelisk* review
**Component:** `src/entities/scenes.py` (`Scene.genEntities`, automatic legacy-door inference)
**Related:** B057, B058, B076

## Defect

B058 conservatively recognizes canonical Roll20 orange (`#ff9900`) as an ordinary door on a
legacy page with no native `doors` objects. That convention is valid across the retained export
fleet, but it is not universal. *Labyrinth of Eyes* uses orange for one grouped moving-wall
assembly. Version 1.15.7 split its 11 paths into 182 Foundry Walls and marked every segment as an
ordinary door.

The Scene therefore presented 182 independent door controls instead of one movable labyrinth
structure. Geometry, movement blocking, and document counts remained valid, so ordinary offline
checks did not distinguish the defect.

## Immutable evidence

- Export: `The Shattered Obelisk_R20Export-1.0.1.zip`, 1,635,933,680 bytes,
  SHA-256 `5EFB53D45D754F0A39BA5EEEE15AEC2EA006DD1BB22BC546217E25A8D23CFF65`.
- Page: `Labyrinth of Eyes`, Roll20 ID `-NbLaTxMJCUgqvBKY3_A`.
- Source: 40 wall-layer paths, all with explicit `barrierType: "wall"`; no native door objects.
- Orange population: 11 paths / 182 segments. Every orange path has `groupwith`; each names the
  other ten members of the same assembly.
- Converted 1.4.1 Scene: 182 ordinary doors.
- Official comparison Scene: zero ordinary doors and one rotating-area interaction.

A read-only census of all 21 retained conversion exports measured 195 non-native pages with
canonical orange, 3,394 orange paths, and 4,835 orange segments. Grouped orange geometry occurs on
exactly one page: *Labyrinth of Eyes*, accounting for exactly these 11 paths / 182 segments. The
other 4,653 orange segments remain eligible for automatic door inference.

## Required handling

- Keep wall/door conversion automatic. RC acceptance remains the final visual/behavioral authority.
- Under automatic canonical-orange inference, retain a path with non-empty `groupwith` as a wall.
- Preserve ordinary automatic conversion for ungrouped orange paths.
- Preserve explicit `--door-color`, `--secret-door-color`, and interactive choices as authoritative
  overrides, including grouped geometry.
- Continue refusing one-way and transparent barriers as doors.
- Log the per-Scene Wall, ordinary-door, secret-door, native-door, and grouped-exclusion counts so
  RC acceptance can reconcile the output without parsing console prose heuristically.

## Resolution

`Scene.pathDoorType()` now owns path-level classification. `Scene.pathIsGrouped()` recognizes the
observed string form and defensive collection forms. Automatic inferred orange is suppressed only
for grouped paths; an explicit color remains authoritative.

The preceding v1.15.7 tag reproduces RED by classifying a grouped orange path as `door: 1`.
The focused B058/B096 suite covers ungrouped automatic doors, grouped automatic exclusion,
explicit ordinary and secret overrides, one-way barriers, and empty/non-empty group shapes.
It passes 51/51; the complete shipping Python 3.8 suite passes 945/945.
