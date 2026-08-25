# B099 - Create-named placement alternative is rejected as ambiguous

**Severity:** High
**Status:** Fixed (v1.15.10)
**Found:** 2026-08-25 during the v1.15.8 full *Shattered Obelisk* conversion
**Component:** `src/entities/items.py` (`_alternativePlacementActivities`, `_mergeSpellConsumption`)
**Related:** B077, B082, B083, B092, B095

## Defect

A pristine conversion with R20Converter 1.15.8 and published Beyond5e 1.2.1 aborts on Oshundo the
Alhoon's limited innate *Wall of Force*:

```text
Cannot select one primary donor activity for limited innate spell 'Wall of Force'
```

The donor contains two complete, mutually exclusive placements for the same cast:

- `utilityWalOfForI`, **Place Panels**, wall template;
- `addCreateDomeGl1`, **Create Dome/Globe**, sphere template.

Both initially consume a spell slot. The source cadence is 1/day, so each placement must instead
consume one use from the same owning Item. `_alternativePlacementActivities()` rejects the pair
because it requires every activity name to begin with `Place `; the equally explicit `Create
Dome/Globe` choice never reaches the existing distinct-name/distinct-template handling.

## Evidence

- R20Converter: v1.15.8, commit `f39872a9ea2478ae74d0e0dae8065ab86351035f`.
- Source export: `The Shattered Obelisk_R20Export-1.0.1.zip`, 1,635,933,680 bytes,
  SHA-256 `5EFB53D45D754F0A39BA5EEEE15AEC2EA006DD1BB22BC546217E25A8D23CFF65`.
- Source Actor: Oshundo the Alhoon, Roll20 ID `-Ncciwo9_7ojsulYL_yt`; *Wall of Force* is 1/day.
- Donor archive: Beyond5e 1.2.1, 14,104,323 bytes,
  SHA-256 `01CF717D0CDD10B8EE579FDA316628CC079EC09AB82718A9D4A06AC212EE3ACC`.
- Disposable donor tree: 116 files / 30,536,029 bytes,
  SHA-256 `98C5914511AF6650D373081214264F2AB8AB87B502FE3B6EAC6956A3453F0F5E`.
- Donor Item: `WallOfForce14III`; rejected activity: `addCreateDomeGl1`.

A hash-bound conversion-only shim changes only
`addCreateDomeGl1.consumption.spellSlot: true -> false`, making **Place Panels** the temporary unique
primary. The same frozen converter then completes and passes Gate A 36/0/0/4. The shim is not a
publication fix: exact placement activities must be restored after conversion.

Frozen R20Converter 1.15.9 independently reproduces the same failure on Acererak during a full
immutable *Tomb of Annihilation* conversion with the pristine Beyond5e 1.2.1 donor. The run exits
1 before writing a manifest or Adventure and names `Wall of Force` at the same predicate.

## Acceptance criteria

- Recognize **Place ...** and **Create ...** as bounded placement verbs when every candidate is a
  complete same-type activity with a concrete, distinct template and slot consumption enabled.
- Keep requiring unique normalized names and unique complete template dictionaries.
- Attach one owning-Item use consumer to every accepted placement and preserve the single 1/day
  pool.
- Continue rejecting repeated names, repeated geometry, unnamed duplicate utility activities,
  damage/concentration/transform follow-ups, and mixed activity types.
- Add the exact Place Panels / Create Dome/Globe pair as a regression and census the donor for any
  newly admitted group beyond this one.
- Prove both Actor-pack and native-Adventure copies preserve both activities and exactly one
  positive self-use consumer apiece.

## Candidate resolution

The placement-name guard now accepts only `Place ...` or `Create ...`; every existing slot,
concrete-template, unique-name, unique-geometry, and same-activity-type guard remains unchanged.
The exact `Place Panels` / `Create Dome/Globe` pair now receives one owning-Item use consumer on
each activity.

A copy-first census of all pristine Beyond5e 1.2.1 spells found two groups accepted by the old
Place-only predicate and seven by the candidate. Exactly five are newly admitted, all explicit
shape alternatives with complete distinct templates: *Prismatic Wall*, *Wall of Force*, *Wall of
Ice*, *Wall of Thorns*, and *Wall of Water*. The old predicate is the RED control (2 -> 7).

Validation: exact B099 regression 1/1, neighboring compendium suite 63/63, and full Python 3.8
suite 964/964 before independent review. Donor-census report: 11,280 bytes, SHA-256
`1533F40EE3BC67621BB74DAEF338CADF73588CA26671123A0DF9D54607D91656`.

Independent Opus QA passed all 6 targets with zero findings and rejected all 9 negative controls.
The 19-file packet remained byte-identical at lock SHA-256
`AFE25CF4922ABA94826FF72B2E2FD2915D5006B5B448360F933FA43E89CC026B`.

The post-review full ToA source-candidate conversion preserves both exact placement activities in
the Acererak Actor pack and native Adventure. Each keeps `spellSlot: true`, a concrete distinct
template, and exactly one positive owning-Item use consumer. The combined logical verifier passes
with SHA-256 `60E6828302DE32C663FD01D6AB631C8AACD074E7CD86425F93D516138481694D`.
The final combined Python 3.8 suite passes 965/965.
