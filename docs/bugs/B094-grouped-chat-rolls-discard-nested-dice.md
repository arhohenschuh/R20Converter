# B094 - Grouped chat rolls discard nested dice results

**Severity:** Minor
**Status:** Fixed in v1.15.6
**Found:** 2026-08-24 during a chat-history bug scan of the July Foundry v13 port
**Component:** `src/entities/chat.py` (`Roll.__init__`, `Roll.toJSON`)
**Related:** ADR-002

## Defect

Roll20 stores a grouped roll as a `G` part with two distinct representations:

- `results` contains only each alternative's aggregate value and discarded state;
- `rolls` contains the nested dice and modifiers that produced those values.

`Roll.__init__()` explicitly ignores `G.rolls`. It builds a synthetic zero-faced die from the
aggregate `results`, and `Roll.toJSON()` then serializes that synthetic part as a `StringTerm`.
The final total and formula survive, but the actual dice, modifiers, and per-die results do not.
This affects both top-level `rollresult` messages and inline rolls embedded in ordinary messages.

## Evidence

Two independent readers measured the retained non-legacy export corpus: PowerShell using .NET ZIP
and JSON APIs, and Python using `zipfile` plus `json`. Both found exactly 78 grouped parts, and all
78 carry nested `rolls` data that the converter ignores.

| Archive | Top-level message | Inline | Total |
| --- | ---: | ---: | ---: |
| Eberron - Rising from the Last War-World | 1 | 0 | 1 |
| Storm over Savage Frontier | 4 | 72 | 76 |
| Wardens of the North - Season 3 | 1 | 0 | 1 |
| **Total** | **6** | **72** | **78** |

The 78 groups contain 150 nested alternatives and 107 individual die outcomes.

Exact reproducer:

- Archive: `Storm over Savage Frontier_R20Export-1.0.1.zip`
- Size: 3,123,137,748 bytes
- SHA-256: `9E11DACBEB11E1594C6A4A32BA8ED1E0BF572528EC8F1EC65C4F2F8D9551EA48`
- Message ID: `-OZKyPMii6sN5t0tzKuG`
- Formula: `{2D4+4}`

The source group records two d4 results, 1 and 4, followed by a `+4` modifier:

```json
{
  "type": "G",
  "rolls": [[
    {"type": "R", "dice": 2, "sides": 4, "results": [{"v": 1}, {"v": 4}]},
    {"type": "M", "expr": "+4"}
  ]],
  "results": [{"v": 9}]
}
```

Running that exact payload through the current `Roll` class produces total 9 but only this term:

```json
{
  "class": "StringTerm",
  "evaluated": true,
  "term": "{2D4+4}"
}
```

The generated tooltip is `Rolling {2D4+4} = +(9)`. It cannot show the two dice or the modifier.
Because `isCrit()` and `isFail()` inspect the aggregate values as if they belonged to a zero-faced
die, grouped natural 20/1 results also cannot be classified from the preserved data.

## Impact

Converted chat history displays the correct aggregate total, so the loss is easy to miss. Opening
or hovering the roll cannot recover how the result was produced, and grouped critical/fumble
highlighting is absent or based on the group total rather than the underlying d20. No actor, item,
scene, or active gameplay data is affected, which keeps the severity Minor.

## Required handling

- Translate the nested alternatives in `G.rolls` instead of treating the aggregate as a fake die.
- Preserve each real die's faces, outcomes, and discarded state, plus nested modifiers.
- Preserve the source formula and aggregate total for both top-level and inline rolls.
- Add regressions for the exact `{2D4+4}` sample and for a keep-high grouped d20 with one discarded
  alternative.
- Re-run the retained-export census and require all 78 grouped parts to retain their nested roll
  evidence.

## Resolution

`Roll.__init__()` now translates a complete Roll20 `G` part into an internal pool containing one
nested `Roll` per alternative. Serialization emits Foundry's native `PoolTerm` contract:
`terms`, `modifiers`, nested Roll JSON in `rolls`, aligned active/discarded `results`, and an
evaluated total. Keep/drop modifiers are translated explicitly; incomplete legacy groups retain
the aggregate fallback rather than aborting chat conversion.

Critical, fumble, and tooltip traversal now recurse through active pool alternatives. The exact
`{2D4+4}` source payload and an independent keep-high d20 control are automated regressions. A
full retained-export replay preserves all 78 grouped parts, 150 alternatives, and 107 die outcomes
with no aggregate-total drift.