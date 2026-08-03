# B036: Innate-spell uses regex matches a single digit — "10/day" becomes 1 use

- **Status**: Fixed in 1.1.0 (F036)
- **Severity**: Minor
- **Found**: 2026-08-03 audit
- **Component**: `src/entities/actors.py:2442` (`addSpells`)

## Defect

```python
match = re.search(r"(\d)(?:/(day|short|long))?", innate.lower())
```

`(\d)` captures exactly one digit. For an innate annotation of `"10/day"` the
first match is the `1`, the optional `/(day|…)` group then fails against the
following `0`, and the result is **1 use with no recovery period** instead of
10/day. Any two-digit innate count ("10/day", "12/day each") degrades the same
way.

Secondary effect: because the period group also fails, `activation.uses.per`
stays empty, `usesFromLegacy` emits no recovery rule, and the (wrong) single use
never comes back on a rest.

## Suggested fix

`r"(\d+)\s*/\s*(day|short|long)"` — require the slash when a period is
expected, capture multi-digit counts, and fall back to a bare `(\d+)` only when
no slash form is present. Regression fixtures: `"3/day each"`, `"10/day"`,
`"1/short rest"`, `"at will"`.
