# B090 - Compendium type mismatch replaces a source weapon

**Severity:** High
**Status:** Fixed in v1.15.3
**Found:** 2026-08-21 during *The Sunless Citadel* v1.15.2 reconversion
**Component:** `src/entities/actors.py` (`createItemInventory`)
**Related:** B050, B054, B062

## Defect

An NPC action that Roll20 explicitly models as a weapon attack can be replaced wholesale by a
same-name compendium Item of another non-loot type. The type-mismatch guard in
`Actor.createItemInventory()` rejects only a donor of type `loot`; it therefore permits an
`equipment` donor to replace a generated `weapon`, despite the adjacent contract saying that a
weapon such as a shovel must not lose its attack and damage properties.

The immutable *Sunless Citadel* source stores Skeleton, Robed's **Shovel** with `attack_flag: on`,
`attack_type: Melee`, range 5 feet, +4 to hit, and 1d6 bludgeoning damage. The observed
R20Converter 1.15.2 run used Beyond5e 2014 Compendium 1.1.11 with
`--no-compendium-overwrite`, matched the same-name PHB Shovel equipment document, and emitted:

- `type: equipment` instead of `weapon`;
- the donor's utility activity instead of the source attack;
- no source weapon damage block.

The release pipeline had to restore the accepted weapon type and source system data before runtime
acceptance. The repaired Shovel then produced its attack and explicit 1d6 damage roll in Foundry.

## Evidence

- Immutable source:
  `TotYP_The Sunless Citadel_R20Export-1.0.0.zip`, 68,153,994 bytes,
  SHA-256 `BA07133AC97DF6A7AE3E3E71D10C866E4A8E4055B25D8DC0D85FA1D47F8E5041`.
- Source Actor ID: `-Kd9E5l6kGQ7hXjGHqdJ`; emitted Actor ID: `ZDdhMjU5ZGE3OTg1`.
- Source repeating action ID: `-KcsyA2QaBVRD7WAYL9G`.
- Broken emitted Item ID: `NDkyNGM2YjI4N2Zi`.
- Current donor confirmation: Beyond5e `1.1.13-rc.3`, repository commit
  `1764b92e845d0fc314324eaeb3ee501e63853491`, still stores Shovel ID
  `DXgo45AVTWTrBeP8` as `equipment` with only activity `utilityShovelIII`. Its `module.json`
  SHA-256 is `CBA0935D2B32C1AC8A9D220B1B8CCC40DD090EE93B15179B6AF23A62A3339001`.
- Semantic differential:
  `reports/baseline-vs-v1.15.2-semantics.json`, SHA-256
  `EBE91ECC7391CB4F4205CACA1F6C10E89915CCB02E2A9BF69C5ED14B52A55154`.
- Independent dry repair:
  `reports/shovel-type-repair-dry.json`, SHA-256
  `B19204CF29312D0C8B954C39AD240B34CC21073220CF44DDBC1896492BE91C02`.

Evidence root:
`D:\Automation_Local\Two_Channel\tftyp-the-sunless-citadel\release\1.2.1-reconversion-001`.

## Required handling

- A same-name compendium match must not change a source Item's semantic document type.
- A source weapon with an attack must remain a weapon with its source attack and damage when the
  donor is equipment, loot, or any other incompatible type.
- Compatible donor enrichment may still apply when it cannot erase source mechanics.
- Type mismatches must be rejected or reported rather than silently accepted.

## Regression coverage required

Convert a source NPC Shovel weapon against a same-name equipment donor. The output must remain a
weapon with one usable attack and 1d6 bludgeoning damage. Add a compatible weapon-donor control to
prove ordinary compendium enrichment still works.

## Resolution

Compendium replacement now permits an exact type match, or a more specific donor when the source
fell back to generic `loot`. Other type mismatches retain the source document and mechanics, use
donor art only, and emit a warning naming both types. Focused regressions prove an equipment donor
cannot replace a source Shovel weapon and a compatible weapon donor still enriches normally.