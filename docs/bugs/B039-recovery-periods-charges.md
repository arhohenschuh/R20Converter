# B039: `RECOVERY_PERIODS` whitelists "charges", which is not a 5.x recovery period

- **Status**: Fixed in 1.1.0 (F039)
- **Severity**: Minor (latent — nothing currently passes `per="charges"`)
- **Found**: 2026-08-03 audit
- **Component**: `src/dnd5e.py:688`, `src/entities/items.py:805` (`ItemUses.PER_CHARGES`)

## Defect

```python
RECOVERY_PERIODS = ("lr", "sr", "day", "dawn", "dusk", "charges", "recharge")
```

dnd5e 5.3.3's `limitedUsePeriods` (`module/config.mjs:1432-1476`) are `lr`, `sr`,
`day`, `dawn`, `dusk`, `initiative`, `turnStart`, `turnEnd`, `turn`, plus the
special `recharge` handled in `UsesField.prepareData`. **"charges" is not among
them** — it exists in 5.x only as a *consumption* type (`config.mjs:1107`). The
recovery `period` field is an unvalidated `StringField`, so an emitted
`{period: "charges"}` entry is stored, ignored by recovery processing, and
renders as a blank/unknown option in the uses UI.

The whitelist exists precisely to keep invalid enum values out of the output
(the F009 pattern); this entry defeats it for the one value the legacy sheet
data actually used (`per: "charges"` in 1.5.6).

Currently latent: `ItemUses.PER_CHARGES` is declared but never assigned, so no
code path passes `"charges"` today. The bug fires the moment someone wires the
legacy `per` field through — which is the obvious next step for consumable
charge data.

## Suggested fix

Remove `"charges"` from `RECOVERY_PERIODS`. Translate legacy `per: "charges"`
as **no recovery rule** (uses that only come back per item description), or
`{period: "day"}` when the item text says "dawn"/"daily". Add the missing 5.x
periods (`initiative`, `turnStart`, `turnEnd`, `turn`) if they are ever needed.
