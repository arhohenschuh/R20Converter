# B057 — converted walls do not restrict movement

**Status:** fixed in v1.9.0
**Severity:** high — every scene in most conversions; tokens walk through every wall
**Component:** `src/entities/scenes.py` → `Scene.genEntities` wall emission
**Found:** 14 Aug 2026, from a Foundry wall inspector screenshot showing *Movement: None*

## Symptom

A converted wall opens in Foundry with **Movement: None** and everything else Normal, and
draws **purple** instead of yellow. Sight, light and sound are blocked correctly; only
movement is not. Tokens walk straight through the wall.

Both states occur in the same world, which is what makes it look random: doors and windows
(the Jumpgate `doors`/`windows` collections) and the optional map-boundary walls are emitted
with `move: 20` unconditionally, while ordinary barriers drawn on the walls layer are not.

## Cause

```python
"move": 20 if page["lightrestrictmove"] or self.getArgument("restrict_movement", False) else 0,
```

`lightrestrictmove` is Roll20's **page-level** "Restrict Movement" toggle from the *legacy*
dynamic lighting system. Two things are wrong with using it.

**1. It is not a boolean.** Measured across all 24 archived exports (668 pages):

| `page.lightrestrictmove` | pages |
|---|---:|
| `null` | **616** |
| `true` | 52 |
| `false` | **0** |

It is never written as `false`. The "off" state and "never set" state are the same value, so
reading it as a boolean turns *"the GM never opened this dialog"* into *"the GM deliberately
disabled movement blocking"*.

**2. Jumpgate does not maintain it.** Every archived export reports `release: "jumpgate"`.
The new engine moved barrier behaviour onto the wall itself as `barrierType`, and the page
flag is a leftover — the 52 pages that carry `true` are the ones authored before the engine
migration. Fleet-wide the walls themselves say:

| `barrierType` | paths | segments |
|---|---:|---:|
| `wall` | 30,013 | 233,065 |
| `oneWay` | 1,740 | 13,426 |
| `transparent` | 334 | 1,678 |

## Measured impact

| | |
|---|---:|
| pages with walls | 409 of 668 |
| pages where `lightrestrictmove` is truthy | **51** (12.5%) |
| wall segments total | 248,169 |
| wall segments converting with `move: 0` | **136,884** (55%) |

Per campaign, every wall segment converted non-blocking on *Curse of Strahd* (11,926),
*Tomb of Annihilation* (20,830), *Princes of the Apocalypse* (12,649), *Waterdeep — Dragon
Heist* (10,804), *Ghosts of Saltmarsh* (4,241), *Lost Mine of Phandelver* (3,103) and every
`tftyp-*` module. *Dungeon of the Mad Mage* is the outlier at 1,279 of 79,780, because 25 of
its 26 walled pages predate Jumpgate and still carry the flag.

## Why every existing gate passed

The walls are all there, correctly positioned, with correct sight/light/sound. G21 checks
token→actor links, not wall properties; nothing in Gate A or Gate B reads `move`. The defect
is only visible by opening a wall's inspector or by walking a token into it — which is why it
survived 21 shipped conversions.

## Fix

`Scene.wallMovementRestriction` replaces the inline expression:

- a barrier on the walls layer blocks movement — `move: 20`;
- a **legacy** campaign may still say no, but only with an explicit
  `lightrestrictmove: False`; `null` and absent no longer mean "off";
- `--no-restrict-movement` forces the old behaviour for a campaign that really was played
  with movement unrestricted;
- `--restrict-movement` still forces blocking and is now the default.

Tests: `tests/test_wall_movement.py`, including the verbatim Wardens page shape
(`lightrestrictmove: null`, 72 of 79 pages).

## Notes

Same shape as B048 and B056: a field whose **meaning changed under Roll20's engine
migration** was still being read the old way, and the pipeline had no check that could
notice. The general lesson is the one in the pipeline doc — a legacy field that a new engine
stopped writing does not read as `false`, it reads as absent, and absent is not a decision.

Existing worlds and modules are not repaired by this change. A world already imported keeps
its `move: 0` walls; repairing it means rewriting the wall documents in place, which is a
separate, opt-in operation.
