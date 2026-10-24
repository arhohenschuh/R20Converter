# B120: Usage limits in NPC feature names are not converted into uses

- Severity: Moderate
- Status: Fixed in v1.16.2
- Observed release: R20Converter 1.16.1, commit cbb0d0e7a9665c43f780c26d3f31ef98f853454d
- Reported: 24 October 2026, Dragoncoast Danger played-world reconversion (`dcd/v130`)

## Reproduction

Convert any OGL NPC whose trait, action, bonus action or reaction name carries a printed limit.
Every such feature arrives with `system.uses = { max: "", spent: 0, recovery: [] }`, and its
activities consume nothing. In Dragoncoast Danger this affects 16 features. 12 come directly from
the converter; the 1.2.2 world, built with an older converter, had the same 12 without uses. The
other 4 are bonus actions restored after conversion for B112. Examples:

| Name pattern | Examples |
| --- | --- |
| `(N/Day)` | *Legendary Resistance (3/Day)*, *Children of the Night (1/Day)*, *Fiendish Rebuke (1/Day)*, *Taunt (2/Day)*, *Healing Light (2/Day)* |
| `(Recharge X–6)` / `(Recharge 6)` | *Sculpted Explosion (Recharge 4–6)*, *Cacophony (Recharge 4–6)*, *Displacement (Recharge 5–6)*, *Possession (Recharge 6)* |
| `(Recharges after a Short or Long Rest)` | *Leadership*, *Dark One's Own Luck*, *Incite the Hunters*, *Second Wind* |

Live check in Foundry 14.369 / dnd5e 6.0.6: using *Taunt (2/Day)* or *Displacement (Recharge
5–6)* posts the card but tracks no use or recharge, so the GM must count limits by hand.

## Expected Behavior

Parse the printed limit generically from the name. Accept en dash, hyphen and the Roll20 mojibake
variant of the dash, and an optional trailing period.

| Printed | `system.uses` | Activity consumption |
| --- | --- | --- |
| `(N/Day)` | `max: N`, recovery `[{ period: "day", type: "recoverAll" }]` | `itemUses` 1 |
| `(Recharge X–6)`, `(Recharge 6)` | `max: 1`, recovery `[{ period: "recharge", formula: "X" }]` | `itemUses` 1 |
| `(Recharges after a Short or Long Rest)` | `max: 1`, recovery `[{ period: "sr", type: "recoverAll" }]` | `itemUses` 1 |
| `(N/Day each)` on innate spellcasting | already handled by spell-level uses; leave unchanged | — |

Keep the printed name unchanged. When a compendium match already has uses, do not overwrite them.

## Regression Requirements

- One fixture per pattern, across trait, action, bonus action (once B112 is fixed) and reaction rows.
- A use followed by a long rest, or a recharge roll, restores the count natively.
- Controls: features without a limit stay unlimited, and compendium-matched features that already
  have uses are unchanged.
- Use renamed actors and features with different identities; the parser must not key on names
  other than the limit suffix.

## Downstream Disposition

Dragoncoast Danger 1.3.0 leaves these features without uses, as in 1.2.2, and documents the
disposition in its FIXLOG. No post-conversion repair is applied.

## Generic Resolution

One shared NPC helper parses the printed daily, recharge-die, and rest suffixes before Item
activities are built. It covers traits, ordinary actions, bonus actions, and reactions, preserving
the existing activation when present. A limited trait without specified timing uses `special`,
not an invented action cost. Dash variants are normalized for parsing only; names are retained.

Existing resource pools are not overwritten. `(N/Day each)` spellcasting quotas remain owned by
the spell-level converter. Every generated use-consuming activity points to its own native Item
use pool. Tests for all sections, dash variants, unaffected features, and preserved pools are in
[test_asset_and_compendium_fixes.py](../../tests/test_asset_and_compendium_fixes.py).
