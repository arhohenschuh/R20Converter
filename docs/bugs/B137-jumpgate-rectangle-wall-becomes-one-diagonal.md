# B137: A Jumpgate rectangle on the walls layer becomes one diagonal Wall

- Severity: High
- Status: Fixed in v1.17.1
- Observed release: R20Converter 1.17.0, commit eae5e7f
- Found: 13 November 2026, while triaging Curse of Strahd intake D1 (the zero-width rectangle)
- Related: [B084](B084-zero-area-jumpgate-ellipse-aborts-conversion.md), [B130](B130-flat-jumpgate-ellipse-outside-walls-aborts-conversion.md)

## Reproduction

Jumpgate stores a rectangle barrier as `shape: "rec"`, `path: null` and two opposite corner points,
for example `[[0, 0], [1890, 1680]]`. The converter used those two points as a polyline, so the
rectangle became one Wall from corner to corner.

*Curse of Strahd* 1.5.7 (SHA-256 `A0319692…ABCE`) has 11 walls-layer rectangles. In the pipeline's
c4 module, *Ravenloft Map 3*, *4*, *5* and *6* each carry a Wall `[150, 150, 2850, 2550]` straight
across the scene. It blocks sight and movement through the middle of each map, and none of the four
map borders exists. Drawings were unaffected, because a rectangle Drawing is built from its width
and height, not its points.

The intake's zero-width rectangle `-OmocrgJSUwA3kBjW6kB` (`[[0, 0], [0, -2.22]]`) did not abort
the conversion; the c4 shim removed it before conversion.

## Resolution

A finite Jumpgate rectangle with two or more corner points becomes its closed bounding box: four
Walls, transformed by the source rotation and scale like every other path. A flat rectangle is one
line segment, so it becomes one Wall instead of overlapping and zero-length Walls. A rectangle whose
corners coincide has no outline and is skipped as debris on every layer, like B130 ellipses.
Legacy SVG rectangles and non-rectangle paths are unchanged.

## Verification

`tests/test_circle_walls.py`: a box yields four closed axis-aligned Walls; a 90-degree rotation
keeps the rotated extent; flat rectangles yield one Wall and a point yields none; rectangle Drawings
are unchanged while point rectangles are skipped. The 1.17.0 source fails six of these cases.

Unmodified Curse of Strahd export against c4: every Wall-count change is +3 per rectangle (1 → 4).
*Ravenloft Map 7-10* has one more Wall, for the 2.22-pixel rectangle the shim had removed. The
cross-map diagonals are gone and the scene borders are present on all four Ravenloft maps.
