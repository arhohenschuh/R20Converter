# B093 - AmbientLights convert full-circle emission to zero degrees

**Severity:** High
**Status:** Fixed in v1.15.5
**Found:** 2026-08-23 during *Out of the Abyss* conversion review
**Component:** `src/entities/scenes.py` (wall-layer AmbientLight creation)
**Related:** B044, B045

## Defect

`Token.lightAngle()` correctly normalizes Roll20's unlimited light arc to 360 degrees. Scene
conversion immediately rewrote that 360 to 0 before storing `AmbientLight.config.angle`. Foundry
uses 360 for omnidirectional emission; 0 is a zero-degree cone. The resulting lights exist and
carry nonzero dim/bright radii, but do not illuminate the Scene as authored.

The same branch also rotated every nonzero angle by 180 degrees. Once 360 is preserved, that
orientation correction must remain limited to narrowed directional cones; a full circle has no
direction to flip.

## Evidence

Immutable source:
`Out of the Abyss_R20Export-1.0.1.zip`, 1,352,732,615 bytes,
SHA-256 `359C772D2082943662F4C48415F92AFD64AC745D52E324DE59B5FAC94601C5F8`.

Applying the converter's wall-layer, light-emission, and positive-radius predicates finds exactly
15 source graphics:

| Scene | Lights |
| --- | ---: |
| Velkynvelve | 9 |
| Lake Shore Roll20 Map | 4 |
| Worm Nursery | 2 |

Eleven source graphics explicitly store `light_angle: 360`; four omit the angle. None is
directional. `Token.lightAngle()` returns 360 for all 15, and v1.15.4's Scene branch converted all
15 to `config.angle: 0`.

## Required handling

- Preserve `FULL_ANGLE` as `AmbientLight.config.angle: 360`.
- Treat an omitted, zero, out-of-range, or malformed source angle as full-circle emission through
  the existing `Token.lightAngle()` normalization.
- Preserve valid narrowed angles.
- Apply the Roll20-to-Foundry 180-degree rotation correction only to narrowed cones.

## Resolution

Scene AmbientLight creation no longer converts 360 to 0. Its defensive exception fallback is 360,
and rotation flips only when the normalized angle differs from `FULL_ANGLE`.

Scene-level regressions exercise the actual AmbientLight branch for explicit 360, omitted angle,
and a 45-degree directional control. The existing Token-level B045 tests remain green.