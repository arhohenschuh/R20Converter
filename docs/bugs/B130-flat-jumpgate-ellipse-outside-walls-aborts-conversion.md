# B130: A flat Jumpgate ellipse outside the wall layer aborts the whole conversion

- Severity: High
- Status: Fixed in v1.17.1
- Observed release: R20Converter 1.17.0, commit eae5e7f
- Found: 13 November 2026, while validating B129 on the *Eberron - Rising from the Last War*
  campaign export (`…_Campaign-1.5.7.zip`, SHA-256 `4431746E…4E7`)
- Related: B076, B084

## Reproduction

After B129 is fixed, the same export stops in the Scene phase:

```text
File "src/entities/scenes.py", line 1290, in pathToPolygonList
    raise ValueError("Path '%s' is a degenerate ellipse" % ...)
ValueError: Path '-OqvauKNVZO2_Z_yyaWx' is a degenerate ellipse
```

The path is a decorative drawing on the `objects` layer of Scene *New Page 1*: Jumpgate
`shape: "eli"`, `path: null`, `width`/`height` 0, and corner points `[0, 0]` and `[-2.08, 0]`.
Its bounding box is 2.08 wide and 0 high, so it has no area and cannot be drawn.

## Cause

B084 classifies a zero-area Jumpgate ellipse as source debris only when every corner point is
identical, and applies that skip only to `walls`-layer paths. A box that is flat in one axis still
reaches the ellipse builder, which correctly refuses zero width or height. Drawing layers had no
debris skip at all, so one stray drawing discards the whole conversion.

The export contains 12 Jumpgate ellipses: 6 valid wall ellipses, 2 valid GM-layer drawings,
3 single-point wall records (already skipped by B084) and this one flat drawing.

## Resolution

`Scene.isZeroAreaJumpgateEllipse` accepts any finite two-or-more-point Jumpgate ellipse whose
corners share an x or a y value: a flat box or a point. The skip is logged with the source path ID
and now applies to drawing layers as well as walls. Nothing replaces the skipped shape; non-finite,
incomplete and legacy-path circles still fail as before.

Regression coverage (`tests/test_circle_walls.py`): flat horizontal and vertical boxes and a point
are debris; a valid box, a non-finite point and a single point are not. A scene with a flat
ellipse plus a valid control on each of the `objects`, `map`, `gmlayer` and `walls` layers emits
exactly the control. Exported HEAD fails all 6 scene-level cases.

Real export: the conversion completes and logs the four zero-area ellipses as skipped.

## Later Report

Curse of Strahd intake D1 (13 November 2026) reported the walls-layer ellipse
`-OmuNHy9W4nPWaAJ0obb` (points `[[0, 0], [0, -0.51]]`) aborting 1.17.0. It is this defect; the
unmodified export logs it as skipped. The zero-width rectangle in the same report did not abort,
but it exposed [B137](B137-jumpgate-rectangle-wall-becomes-one-diagonal.md).
