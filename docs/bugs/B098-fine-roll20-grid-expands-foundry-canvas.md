# B098 - Fine Roll20 snapping expands the Foundry canvas without explicit telemetry

**Severity:** Moderate
**Status:** Open owner-pickup request
**Found:** 2026-08-25 during official-versus-converted *Shattered Obelisk* review
**Component:** `src/entities/scenes.py` (`Scene.__init__`, grid multiplier)
**Related:** B060

## Request

Keep conversion automatic, but make the sub-0.5 snapping path explicit and measurable so RC
acceptance can decide whether source-faithful fine placement is playable at Foundry scale.

## Evidence

Foundry rejects grid sizes below 50 pixels. R20Converter therefore multiplies every Scene
coordinate when `70 * snapping_increment < 50`. In the retained *Shattered Obelisk* export:

- `Spawn Hollow` uses `snapping_increment: 0.125`; its converted grid area is 64 times the
  official comparison Scene.
- `Mire of Doubt` uses `snapping_increment: 0.125`; its converted grid area is about 14.945 times
  the official comparison Scene.

This is not automatically wrong: it preserves Roll20's fine placement grid and all relative
coordinates. The problem is that the scale-changing branch is silent and its large canvas becomes
visible only during RC review.

## Acceptance criteria

- Preserve automatic conversion and current coordinate consistency by default.
- Emit a structured/per-Scene warning whenever `snapping_increment < 0.5`, including source width,
  height, snapping increment, original grid pixels, multiplier, output width/height, output grid
  pixels, and source/output grid area.
- Add an optional explicit scale override keyed by stable Roll20 page ID; never infer it from an
  official module or page name.
- Apply one transform to background, Tiles, Tokens, Walls, lights, drawings, and padding; prove all
  surfaces use the same multiplier.
- Add controls for 0, 0.125, 0.5, and 1.0 snapping increments and reject non-finite/negative values.
- Make the conversion report list every scaled page for downstream RC acceptance.
