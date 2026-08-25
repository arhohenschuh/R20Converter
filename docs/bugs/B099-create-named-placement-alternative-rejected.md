# B099 - Create-named placement alternative is rejected as ambiguous

**Severity:** High
**Status:** Open owner-pickup request
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
