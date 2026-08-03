# B042: 3-digit hex colors expand with ×16 instead of ×17

- **Status**: Open
- **Severity**: Minor (cosmetic: slightly-off colors on walls, drawings, lights, tints)
- **Found**: 2026-08-03 audit
- **Component**: `src/entities/base.py:462-467` (`Entity.color`)

## Defect

```python
if len(val) < 6:
    rgb = tuple(int(val[i:i+1], 16) * 16 for i in (0, 1, 2))
```

CSS shorthand expands each nibble by *repetition*: `#abc` ≡ `#aabbcc`, i.e.
`nibble * 17` (0xA → 0xAA = 170). Multiplying by 16 yields `#a0b0c0`, so every
short-form color is a shade darker than authored, and `#fff` becomes `#f0f0f0`
instead of white. Affects everything routed through `Entity.color`: grid color,
background color, wall/door colors (and therefore the `--door-color` matching if
a user passes a short form), text and path drawings, token tints and light
colors.

## Suggested fix

`int(c, 16) * 17`, plus handle the 4-digit `#rgba` form by ignoring the alpha
nibble rather than misreading it. One-line regression:
`Entity.color("#fff") == "#ffffff"`.
