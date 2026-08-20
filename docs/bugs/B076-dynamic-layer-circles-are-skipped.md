# B076 - Dynamic-layer circles are skipped

**Severity:** High
**Status:** Fixed in v1.15.0
**Found:** 2026-08-20 during Tomb of Annihilation v1.14.0 qualification
**Component:** `src/entities/scenes.py` (dynamic-layer path emission)
**Related:** B059 (incorrect quadratic flattening; a separate curve defect)

## Defect

`Scene.createScene()` identifies Roll20 ellipse/circle paths, logs `Circle in the dynamic
layer! Not supported!`, and skips them. Conversion succeeds with no Wall documents for that
source path. These paths are often intentional circular sight barriers around pillars, wells,
gears, and encounter areas, so omitting them changes line of sight across the map.

## Evidence

The immutable Tomb of Annihilation export contains 224 dynamic-layer circles across 27 Scenes:
197 one-way magenta barriers and 27 ordinary blue barriers. Source-bound flattening at four
segments per cubic curve produces 3,584 deterministic Wall children. The unmodified v1.14.0
conversion emits none of them and logs all 224 as unsupported.

All 224 are vision-only because their source Pages do not restrict movement. This is not B059:
B059 emits the wrong vertices for a supported quadratic path, while B076 discards the entire
circle.

## Fix contract

- Flatten every circle/ellipse curve deterministically and close the polygon.
- Apply the same scale, rotation, translation, barrier type, direction, sight, and movement
  semantics as other dynamic-layer paths.
- Derive stable Wall IDs from the source path ID plus segment ordinal.
- Reject degenerate or non-finite geometry rather than writing invalid Walls.
- Report source circles and emitted segments as conserved populations instead of warnings.

## Regression coverage required

Cover ordinary and one-way circles, non-uniform scale, rotation, movement-enabled and
vision-only Pages, stable IDs, closed geometry, and a degenerate negative control.

## Resolution

`Scene.pathToPolygonList()` now samples every cubic at four fixed subdivisions and closes the
polygon. `transformPathPoint()` applies scale and center rotation; `createPathWall()` preserves
barrier semantics and derives `Entity.strToID("<source>:circle-wall:<ordinal>")`. Non-finite,
incomplete, or degenerate geometry aborts. `tests/test_circle_walls.py` covers every contract, and
the immutable ToA verifier proves 224 circles / 3,584 unique Walls.