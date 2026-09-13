# B111: NPC pact trait loses its shared short-rest spell slots

- Severity: High
- Status: Open; repository owner triage and implementation required
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