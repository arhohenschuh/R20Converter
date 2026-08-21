# B084 - Jumpgate ellipse bounds are treated as a polygon

**Severity:** High
**Status:** Fixed in v1.15.2
**Found:** 2026-08-20 during Eberron Setting v1.15.1 candidate conversion
**Component:** `src/entities/scenes.py` (wall-path emission)
**Related:** B059, B076

## Defect

Jumpgate stores an ellipse as `shape: "eli"` with two bounding-box corner points. The B076 parser
treated those corners as a two-vertex polygon, then correctly rejected the result as a degenerate
circle. Its fallback ellipse generator ran only when fewer than two points existed, the opposite
of the observed source shape.

An exhaustive scan of the immutable Eberron Setting export finds 12 wall-layer ellipses across
Strider Airship and The Recluse:

- eight have finite nonzero bounds and should emit 16 Walls each (128 total);
- four have zero width, zero height, and two identical `[0, 0]` points, so no valid Wall can be
  recovered.

The first zero-area record to abort was transparent path `-OfdWqaRPUGfua7D38jL`. After its narrow
skip, the next nonzero bounding-box ellipse also aborted, exposing the systemic parser defect.

## Fix contract

- Interpret finite Jumpgate ellipse points as bounding-box corners and sample a closed 16-segment
  ellipse from their extrema.
- Classify a zero-width, zero-height ellipse with at least two finite identical points as source
  debris; log and skip its exact source path ID at the wall-emission boundary.
- Keep generic degenerate, incomplete, non-finite, and nonzero circle geometry fail-closed.
- Do not emit a zero-length Wall or fabricate replacement geometry.

## Regression coverage required

The exact zero-area shape must classify as source debris. A measured nonzero two-point bounding box
must produce 17 closed polygon points (16 segments). Existing B076 controls for ordinary, one-way,
degenerate, and non-finite circles must remain green.

## Resolution

Jumpgate ellipse parsing now derives bounds from source points and samples the same deterministic
16-segment closed geometry used by the circle contract. `Scene.isZeroAreaJumpgateEllipse()` handles
the four impossible records before polygon conversion. The independent source audit proves 8/8
reconstructions, 128 segments, 4/4 debris classifications, and zero unexpected failures.