# B035: `hlbonus == ""` is a comparison, not an assignment — spurious spell scaling "+ 0"

- **Status**: Open
- **Severity**: Minor
- **Found**: 2026-08-03 audit
- **Component**: `src/entities/actors.py:2473-2480` (`addSpells`)

## Defect

```python
if hldie == "0":
    hldie = ""
    hldice = ""
if hlbonus == "0":
    hlbonus == ""          # <-- no-op comparison; should be an assignment
if hldie != "" or hldice != "" or hlbonus != "":
    scaling.formula = hldie + hldice + ((" + " + hlbonus) if hlbonus != "" else "")
    scaling.mode = ItemSpellScaling.LEVEL if level > 0 else ItemSpellScaling.CANTRIP
```

A spell whose sheet stores `spellhlbonus = 0` (the OGL sheet writes `0` freely)
keeps `hlbonus == "0"`, so the guard on the next line fires and the spell gets
`scaling.formula = " + 0"` and a scaling mode it should not have.
`dnd5e.damageScaling` then emits `mode: "whole", formula: " + 0"` on the damage
part — every upcast appends a cosmetic `+ 0` to the roll, and spells with no real
scaling are marked as scaling.

## Suggested fix

`hlbonus = ""` (assignment). Cheap regression: assert a spell with
`spellhldie=0, spellhlbonus=0` produces `scaling == ("", 1, "")`. Linting the
repo with `pyflakes`/`ruff` would have flagged this as a useless expression
statement.
