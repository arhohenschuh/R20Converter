# B060 — Scenes migrate with Fog of War exploration disabled

**Severity:** High
**Status:** Fixed in v1.11.1
**Found:** 2026-08-20 during *Curse of Strahd* module acceptance

## Defect

`Scene` emitted the removed `fog.exploration` boolean and derived `tokenVision` from legacy
Roll20 lighting flags. Foundry 14 stores exploration as `fog.mode`; its migration produced
`mode: 0` (None), so players did not retain explored areas. Pages without the expected legacy
lighting combination could also disable Scene Token Vision and make every Token sight setting
ineffective.

## Evidence

All 50 source Scenes and all 50 Adventure Scene copies in the measured *Curse of Strahd*
candidate had `fog.mode: 0`. The accepted *Lost Mine of Phandelver* repair independently
established `fog.mode: 1` as Individual exploration and changed all 10 source and Adventure
copies from 0 to 1.

The converter output was:

```json
{"tokenVision":"derived from legacy page flags","fog":{"exploration":"boolean","reset":"timestamp","overlay":null}}
```

Foundry 14 requires:

```json
{"tokenVision":true,"fog":{"mode":1,"reset":"timestamp","colors":{"explored":null,"unexplored":null}}}
```

## Fix contract

- Enable Scene Token Vision by default on every converted Scene.
- Emit current Foundry 14 fog fields directly and default to Individual exploration.
- Retain explicit `--disable-fog` as a world-export escape hatch that writes `fog.mode: 0`.
- Reject module preparation and exact-package QA unless every source and Adventure Scene has
  `tokenVision: true` and `fog.mode: 1`.
- Cover the full serialized Scene shape, including absence of legacy `exploration` and `overlay`.