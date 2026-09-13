# B059 — Quadratic paths use their control point as an emitted wall vertex

**Severity:** Minor for the measured campaign; potentially higher on freehand-heavy maps  
**Status:** Fixed in 1.16.1
**Found:** 2026-08-14 during a first-release barrier audit

## Original Defect

Roll20 stores a quadratic Bézier as `Q(controlX, controlY, endX, endY)`. The curve normally
passes toward the control point but does not pass through it. `Scene.pathToPolygonList()` appends
both the control point and endpoint as polygon vertices. The wall loop then emits straight
segments through both points.

That is not curve flattening. It replaces one quadratic curve with two chords that pass through
an off-curve point, so the Foundry barrier may bulge outside the authored curve.

## Evidence

One immutable source path has commands:

```json
[["M", 0, 0], ["Q", 0, 0, 0.5, 0], ["L", 1, 0]]
```

Three common counters disagree:

| Unit | This path | Campaign total |
| --- | ---: | ---: |
| `L` commands | 1 | 11,684 |
| source points minus one | 2 | 11,685 |
| converter attempted Walls (`len(polygon) - 1`) | 3 | 11,686 |

The measured path is one pixel wide and zero pixels high, so the visible impact is negligible.
It nevertheless exposed that an acceptance gate counting source segments can disagree with the
converter even when both readers are internally correct.

## Required handling

- Gates must name their unit and use converter-attempted Wall count for raw-output comparison.
- Emitted Wall count may be lower only when every skipped segment is itemized by reason.
- A future fix should flatten quadratic/cubic curves at a declared tolerance or retain them as a
  supported Foundry shape. It must not silently route through the control point.
- Add regression coverage with a non-collinear quadratic whose true curve does not pass through
  the control point.

This finding does not change legacy-door classification. Stroke color semantics remain governed
by B058.

## Generic Resolution

Quadratic and cubic commands now use bounded adaptive subdivision at a declared tolerance of
0.5 output pixels before integer rounding and optional user-requested wall simplification.
The tolerance accounts for path scaling and automatic grid enlargement. Chained curves start at
the preceding endpoint; open cubics are not forcibly closed or converted to ellipse drawings.
Recognizable legacy ellipses retain their native shape classification.

All Wall paths and simplification neighbors now use the same scale-and-rotation transform.
Already-flattened drawings disable additional Bezier smoothing. Tests include non-collinear
quadratics, open and chained cubics, malformed input, bounded approximation error, nonuniform
scale, rotation, fine grids, and unchanged legacy circle controls. No module or path identity
selects this behavior.
