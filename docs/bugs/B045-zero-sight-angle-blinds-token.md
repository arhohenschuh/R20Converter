# B045: Unlimited Roll20 vision converts to a zero-degree cone, blinding the token

- **Status**: Fixed in 1.7.0 (F045)
- **Severity**: Critical (player-visible — an affected token is completely blind, regardless of senses or lighting)
- **Found**: 2026-08-04, live diagnosis against *Wardens of the North* on Foundry 14.365
- **Component**: `src/entities/actors.py:215-227` (`sightAngle`), `:229-252` (`lightAngle`), emitted at `:329`

## Defect

```python
@staticmethod
def sightAngle(token):
    legacy = token.get("legacy_lighting_enabled", defaultLegacyEnabled)
    angle = 0
    if legacy:
        angle = token.get("light_losangle", angle)     # absent key -> 0
    else:
        if token.get("has_limit_field_of_vision", False):
            angle = token.get("limit_field_of_vision_total", angle)
        else:
            return 0                                    # "no limit" -> 0
    ...
```

Roll20 expresses *unrestricted* vision as the **absence** of a field-of-vision
limit. The converter maps that to `0` and writes it straight into the token:

```python
"sight": { ..., "angle": self.sight_angle, ... }
```

In Foundry, `sight.angle` is the **aperture of the vision cone in degrees**, and its
schema default is 360 (`common/documents/token.mjs`):

```js
angle: new fields.AngleField({initial: 360, normalize: false}),
```

So `0` does not mean "unlimited" — it means a **zero-degree cone**. The token has
sight enabled, a valid range and correct detection modes, and still sees nothing.
The two meanings are exact opposites, which is why this reads as correct code.

`lightAngle()` has the identical shape and the same consequence for emitted light
(`light.angle: 0` is a zero-degree emission arc).

## Measured

*Wardens of the North*, read live:

| Population | `sight.angle == 0` | `== 360` |
|---|---:|---:|
| Prototype tokens (all actors) | **394 of 394** | 0 |
| Placed tokens, N21 Hrakhamar | 0 | 52 |
| Placed tokens, N22 The Deep Delve | **2** | 190 |
| Placed tokens, whole world | 2 of 1,980 | 1,978 |

The two blind placed tokens were both **player characters**. Placed tokens were
mostly repaired by an earlier pass; the **prototypes were not**, so every token
newly dragged onto a scene is born blind. That is the shape this defect takes in
an already-repaired world — in fresh converter output every token carries 0.

## Why it hid for so long

A zero-degree cone is only observable on a scene where vision actually restricts
what is drawn. On a scene with `globalLight.enabled = true` — 19 of this world's
79 — everything is lit and visible regardless, so the defect is invisible. It
surfaces only on the 2 scenes that are fully dark, and there it presents as
"darkvision is broken", which points the investigation at senses (B044) rather
than at geometry.

## Suggested fix

Return **360** rather than 0 for the unlimited case, in both `sightAngle()` and
`lightAngle()`:

- non-legacy: `if not token.get("has_limit_field_of_vision", False): return 360`
- legacy: default `angle = 360`, and treat a stored `0` as 360
- guard the parsed value: an out-of-range or non-numeric angle should fall back to
  360, not to 0

Same for `lightAngle()` with `has_directional_bright_light`.

## Regression tests

- A token with no field-of-vision limit converts to `sight.angle == 360`.
- A token with `has_limit_field_of_vision` and `limit_field_of_vision_total = 90`
  converts to `sight.angle == 90`.
- A legacy token with no `light_losangle` key converts to `sight.angle == 360`.
- No emitted token has `sight.angle == 0` while `sight.enabled` is true.
- The same four for `light.angle`.

## Relationship to B044

Independent root causes that produce the same symptom, which is why fixing B044
alone did not restore vision. B044 sets *how far* a token can see; B045 sets
*through what arc*. A token needs both: the elf PCs here had a corrected 60 ft
darkvision and still saw nothing until the angle was moved off 0.
