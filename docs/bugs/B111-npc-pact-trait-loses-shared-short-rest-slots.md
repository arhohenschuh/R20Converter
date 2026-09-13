# B111: NPC pact trait loses its shared short-rest spell slots

- Severity: High
- Status: Fixed in 1.16.1 with generic source-contract conversion
- Observed release: R20Converter 1.15.17, commit b0765550fa9bcb9a553fa920ffb794a25b90921e
- Reported: 13 September 2026, Out of the Abyss Pipeline-11

## Reproduction

Convert the owner-supplied Out of the Abyss R20Exporter 1.4.1 archive with the published
1.15.17 binary, dnd5e 5.3.3 and Beyond5e 1.4.1. Source archive SHA-256:
`12E57C593791D75A94FE0F7590C84F34286CC0E9E6034A5D62915D7C16FF3462`.

Source character `-M1JGgyqjBHjbj5hOKry`, Narrak, has the explicit Spellcasting description:

> Narrak has two 2nd-level spell slots, which he regains after finishing a short or long rest.

It names three cantrips and six leveled warlock spells. The output instead retains the source
sheet's conventional 4/3/2 slot values and has no shared two-use short-rest casting resource.
The printed trait and scalar sheet fields conflict; blindly inheriting the conventional pool
changes both casting capacity and recovery.

The successful raw conversion is retained under:

```text
D:/Automation_Local/Work/DnD5e/Foundry_Work/out-of-the-abyss-1.5.0-rc.1-reexport-002/
  reports/driver-conversion-005.json
  raw-conversion-005/out-of-the-abyss/
  reports/narrak-source-repair-plan-001.json
  reports/narrak-source-repair-zero-001.json
  reports/native-mechanics-003.json
```

Only copy the raw packs to a disposable directory before inspecting them logically.
The conversion completed; the shared driver separately stopped at its default installer-card
gate. That later presentation gate is not this defect.

## Expected Behavior

Preserve the explicit source contract: six leveled spells share two casts, cast at 2nd level,
recover on a short or long rest, and have no additional conventional slot pool. Cantrips remain
at will. Preserve every source spell, activity and unrelated resource.

## Fix Suggestion

In the owning NPC spellcasting conversion path, recognize explicit shared-slot traits including
slot count, spell level and rest recovery. Reconcile the printed trait with scalar sheet values;
report unresolved conflicts instead of silently selecting a conventional caster progression.
Use structural source evidence, not a Narrak name exception.

A bounded module-only restoration uses the accepted prior Adventure's Spellcasting feature
as a two-use `sr` recovery pool. Exactly six primary casting activities consume one use of that
feature with spell-slot consumption disabled. The pinned dnd5e implementation supports fixed
casting level through `flags.dnd5e.spellLevel: {value: 2, base: <original spell level>}`; its
activity configuration/scaling code was inspected and native use was verified. This is evidence
for the repository owner, not a prescribed general converter design.

Required regressions include conflicting 4/3/2 scalar values, missing/ambiguous source traits,
all six consumers sharing one pool, unchanged cantrips and other feature resources, exhaustion
after two casts, 2nd-level scaling of 1st-level spells, short/long-rest recovery, module/Adventure
projection parity, and native dnd5e consumption. Include a non-pact NPC control.

No converter implementation, tests, build, version, commit or publication was changed by
Pipeline-11. The module repair does not close this converter defect.

## Generic Converter Resolution

Version 1.16.1 recognizes an explicit shared-slot count, casting level, and short-rest recovery
clause in source Spellcasting or Pact Magic traits. It reuses the emitted source feature as a
shared `itemUses` resource, suppresses contradictory conventional progression, and binds only
source-listed ordinary leveled spells after donor enrichment. Fixed casting level is retained
through the native dnd5e spell-level flag. Short-rest recovery also participates in long rests.

Primary selection reuses the existing structural casting rules. A forward activity targeting the
same Item's direct cast remains free: native dnd5e forwarding disables resource and slot
consumption. The converter does not select by spell, NPC, module, page, path, hash, or document ID.

Tests cover renamed source identities, both output modes, shared consumers, unchanged cantrips
and unrelated resources, malformed or duplicate contracts, unlisted spells, insufficient casting
levels, and ambiguous activity selection. The original exported actor and a renamed counterpart
exercise the same conversion path. Targeted module restoration remains separate historical
evidence, not an implementation dependency.

## Release Verification (13 September 2026)

- The shipping Python 3.8 suite passes all 1,104 tests, including the
  [shared-slot regressions](../../tests/test_dnd5e_schema_diff.py) and the existing
  [donor/resource controls](../../tests/test_asset_and_compendium_fixes.py).
- The exact v1.16.1 Windows archive converts the original fixture, a renamed campaign/NPC
  counterpart, and world-mode output. The six shared consumers and Actor/Adventure embedded
  relationships agree. Published v1.16.0 reproduces the old 4/3/2 conventional-slot defect.
- Foundry 14.367 with dnd5e 5.3.3 Legacy imports the frozen module through the native Adventure
  workflow and passes pre/post-import Gate B and reload checks. All six native actor-sheet casts
  consume one shared use.
- A disposable native actor exhausts the pool after two casts and rejects the third. Cantrips and
  the forward activity remain free even when exhausted. Short and long rests restore the pool;
  first-level spells receive one level of fixed upcast scaling, while second-level spells receive
  none. Exhausted state survives reload.
- Stopped-storage inspection confirms the saved pool, all six fixed-level flags, embedded
  parent-child closure, and cleanup of the probe and messages. No content repair was applied to
  the converter output to obtain these results.

Evidence is retained under `D:/Automation_Local/Work/DnD5e/Foundry_Work/r20converter-open-bugs-001/`:
`evidence/native-adventure-import-001.json`, `evidence/native-casts-001.json`,
`evidence/native-resource-verify-002.json`, and `evidence/native-stopped-persistence.json`.
The first resource verifier attempt stopped on an undefined-field versus JSON comparison before
creating a probe; its corrected retry compares the same serialized state without altering output.
This is focused converter acceptance, not a full-campaign acceptance claim. Independent review
was waived by the owner and is not reported as performed.