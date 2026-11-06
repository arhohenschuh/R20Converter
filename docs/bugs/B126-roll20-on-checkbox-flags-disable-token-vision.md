# B126: Roll20 `"on"` checkbox flags disable token vision

- Severity: Moderate
- Status: Fixed in v1.17.0
- Observed release: R20Converter 1.16.4; the raw flag reads predate the B0xx register
- Found: 6 November 2026, while triaging B125 on the pinned Dragoncoast Danger export

## Reproduction

Roll20 stores some token checkboxes as the string `"on"` instead of JSON `true`. The pinned
Dragoncoast Danger export (Jumpgate) has `has_bright_light_vision`, `has_low_light_vision`, and
`has_night_vision` set to `"on"` on 15 default tokens and 5 placed graphics, and to `true` on one
of each.

`Token.hasSight` returned the raw value, so the token was written as `sight.enabled: "on"`.
Foundry's `BooleanField` casts every string except `"true"` to `false`. Converted tokens whose
Roll20 vision was on therefore had vision switched off. The same raw reads affected light
emission, the field-of-vision and directional-light switches, the legacy-lighting selector, name
and bar visibility, and Scene global light. `fliph`/`flipv` used Python `bool()`, so `"off"`
mirrored the token.

## Cause

`src/entities/actors.py` (`Token`) and `src/entities/scenes.py` read Roll20 checkbox fields
directly as booleans.

## Resolution

`Entity.roll20Flag` parses `true`/`"on"`/`"true"`/`"1"`/`"yes"` as true and everything else,
including `"off"` and `""`, as false. Every `Token` checkbox read, the placed-token name check, and
Scene global light now use it.

Regression coverage (`tests/test_dnd5e_target.py::TestB126RollTwentyFlags`) includes the parser
truth table, sight for `"on"`/`true`/`""`/`false`, `"off"` without mirroring, and the string
legacy-lighting selector. Exported HEAD writes `sight.enabled: "on"` and `scaleX: -1` for the
same inputs.

Pinned export: HEAD stores 15 prototype and 5 placed `"on"` sight values. The fix stores
`true` for all 16 prototype and all 6 placed tokens where Roll20 enabled vision. Native dnd5e 6.0.6
replay differs from HEAD only in those 15 prototype sight values.

## Already Converted Outputs

Outputs from 1.16.4 and earlier may contain `sight.enabled: false` (after Foundry cast) where
Roll20 enabled vision. Check them through the post-conversion workflow. The converter cannot
recover the original Roll20 value from a converted world.
