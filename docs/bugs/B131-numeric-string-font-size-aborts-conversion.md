# B131: A text object whose font size is a numeric string aborts the conversion

- Severity: High
- Status: Fixed in v1.17.1
- Observed release: R20Converter 1.17.0, commit eae5e7f
- Reported: 13 November 2026, Curse of Strahd 1.4.0 conversion intake D2
  (`Curse of Strahd-1.5.7.zip`, SHA-256 `A0319692…ABCE`, R20Exporter 1.5.7; also in the 1.0.0 export)
- Upstream copy filed by mistake: kakaroto/R20Converter#99

## Reproduction

Roll20 stores most text sizes as numbers (`"font_size": 12`), but some text objects carry a numeric
string. The reported export has 13 such objects on six pages; the other 37 are numbers.

```json
{"type": "text", "id": "-OoCmQphDPe-5Apod1lC", "font_size": "12", "font_family": "Candal", "text": "GM Note: ..."}
```

The Scene phase stops on the first one and the whole conversion is discarded:

```text
File "src/entities/scenes.py", line 601, in __init__
    drawing["fontSize"] = text["font_size"] * grid_multiplier
TypeError: can't multiply sequence by non-int of type 'float'
```

## Cause

Generic converter defect. The text branch multiplied the raw source value and copied it into the
Drawing. `getTextSize` already tolerated strings through `int(...)`; the Drawing paths did not.

## Resolution

`Scene.textFontSize` reads the size once per text object: a finite positive number or numeric string
is used as a number (integral values stay `int`), and anything else becomes the existing 12-point
default with a warning naming the text ID. Size measurement, the Drawing and the scaled `fontSize`
all use that value. Numeric sources produce the same output as before.

## Verification

`tests/test_scene_exploration.py`: `"12"` and `"10.5"` convert like numbers; `"large"`, `""`,
`None`, `"-4"` and `"nan"` use the default and warn; a numeric control is unchanged. The 1.17.0
source fails all seven string cases.

The unmodified reported export converts completely (see B132). All 41 non-empty text Drawings carry
a numeric `fontSize`.
