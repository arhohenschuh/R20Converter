# Roadmap — dnd5e 5.x native output

**Goal:** R20Converter emits documents that Foundry **v13+** and dnd5e **5.x** load
with **zero migration**.

Decision record: [ADR-008](docs/adr/ADR-008-emit-dnd5e-5x-natively.md).

## Current invariant: no downstream structural repair

**Adopted direction after v1.11.0:** a successful conversion must not require an external
tool to normalize storage, activity consumption, spell ownership, or schema migrations.
Campaign-specific content policy may remain downstream; generic document correctness belongs
in R20Converter.

Adopt this incrementally rather than rewriting the converter:

1. **Done in v1.11.1-v1.11.2:** move Scene fog, Token name visibility, spell ownership, and
  activity consumption into their converter owners.
2. **Done in v1.12.0:** make the recursive LevelDB writer preserve ActorDelta and ActiveEffect
  children with bidirectional parent/child conservation checks.
3. **Done in v1.13.0:** complete actor resource contracts: spell-slot capacity and availability,
  item-use pools, and activity consumption must agree without downstream repair.
4. **Done in v1.14.0:** assemble self-contained modules, internalizing executable compendium
  dependencies and embedded HTML artwork while preserving campaign-authored policy downstream.
5. **Done in v1.15.0:** close ToA's systemic follow-ups: circular Wall geometry, donor consumer
  reconciliation, source cadence inference, quality-aware system summon localization, and known
  Roll20 placeholder rejection.
6. **Done in v1.15.2:** segment multiple innate cadence markers on one Roll20 trait line without
  broadening list recognition into ordinary prose, and select a unique initial donor cast without
  charging concentration or transform follow-up activities; reconstruct two-point Jumpgate
  ellipse bounds, skip exact zero-area debris, retain strict rejection for malformed geometry, and
  close prose RollTable dependencies from declared custom-compendium packs; normalize raw Markdown
  links and undeclared relative HTML image paths before module assembly; preserve source Macros in
  both a module pack and the native Adventure; stamp every primary source document before the
  native Adventure snapshot is built.
7. **Done in v1.15.3:** keep explicit source Item types authoritative across same-name compendium
  matches, and normalize outer whitespace at NPC Item-name boundaries.
8. **Done in v1.15.4:** preserve bounded alternative placement activities when each is a complete
  cast drawing from the same limited innate Item-use pool.
9. **Done in v1.15.5:** preserve omnidirectional Scene AmbientLights as 360-degree emitters and
  limit rotation correction to narrowed directional cones.
10. **Next:** add a native Foundry 14 module target profile. Keep the core-13 profile as rollback until
  several real exports prove canonical document, activity, folder, Scene, token, and runtime
  parity with Foundry's own migration.
11. Promote native-v14 module output only after frozen-binary conversion, zero-migration launch,
  clean Adventure import, and independent migration-parity review.

World LevelDB output remains out of scope for this stage: worlds retain the established NeDB
migration path until module parity is demonstrated and the operational value justifies the
additional native-storage surface.

## Conventions

| Prefix | Meaning |
|---|---|
| **R1–Rx** | Roadmap steps. One step per minor version. |
| **B001–Bxxx** | Bugs found along the way, in the converter or in our own tests. |
| **F001–Fxxx** | Fixes. Each references the bug it closes. |

Every bug gets a regression test before its fix is accepted. A bug found in a
*test* counts — a test that ratifies a broken implementation is a defect.

## Why this work exists

The Foundry **core** schema port (ADR-002) is complete. The **dnd5e system** layer
is not: every item is emitted in dnd5e ~1.5.6 shapes. Unlike Foundry's deleted v9
migrations, dnd5e's migrations still exist — which is worse than their absence,
because they run, report success, and corrupt. Measured while hand-repairing two
converted 760 MB modules:

- The migration **never gives weapons an attack**. dnd5e builds the default attack
  in `WeaponData#_preCreate`, which fires on document *creation*; a migration is an
  *update*. 479/479 and 742/742 spells migrated with working activities; **393/393
  and 524/524 weapons migrated with zero**.
- The migration can **silently destroy damage**. It consumes legacy
  `damage.parts` and stamps `_stats.systemVersion`, but for a subset of documents
  writes an empty `damage.base` back. A shim rebuilds it in memory, so the *live*
  document reads correctly while the *stored* one holds nothing. 390 weapons with
  dice live, **293 stored**.

## Steps

| Step | Version | Title | Output changes? | Status |
|---|---|---|:--:|---|
| **R1** | 0.15.0 | Foundation — `src/dnd5e.py`, shape builders, tests | No | **Done** |
| **R2** | 0.16.0 | The Switch — atomic dnd5e 5.x emission | Yes, breaking | **Done** |
| **R3** | 0.17.0 | Cleanup — origin documents, actor fields, remaining `_stats` | Yes | **Done** |
| **R4** | 1.0.0 | Acceptance — real exports through a real Foundry | No | **Done** |

---

### R1 · 0.15.0 — Foundation ✅

No output change. The module is added and unit-tested; nothing imports it yet, so
emitted output is byte-identical to 0.14.0.

- `src/dnd5e.py` — single source of truth for dnd5e version numbers and data
  shapes, mirroring `foundry.py`. Constants read out of the dnd5e 5.3.3 source
  (`module/config.mjs`, `module/data/shared/damage-field.mjs`,
  `module/documents/activity/attack.mjs`) rather than inferred.
- `DamageData` builder; damage-formula parser that survives the degenerate
  real-world cases (`1d0` nets, flat `1` torches, `1d1`); damage-type
  normalisation for the dirty values Roll20 emits.
- Activity builders — attack, save, damage, heal, utility — with deterministic
  16-character ids so repeat conversions are byte-identical.
- Ability-modifier extraction under the invariant that the **printed damage total
  is unchanged**.
- `_stats` builder. The converter previously emitted none at all.
- 112 new tests. Suite: **137 → 249**.

**Gate:** suite green · no emitter imports `dnd5e` · version bumped · changelog ·
ADR-008 written.

---

### R2 · 0.16.0 — The Switch ✅

**One atomic change.** Sliced any finer, the converter would emit documents that
are neither old enough for dnd5e's migrator nor complete enough for 5.x — strictly
worse than today. Removing `damage.parts` before `activities` exist leaves damage
with nowhere rollable to live.

In scope, all in one commit:

- `system.type = {value, baseItem}` replaces `weaponType` / `armorType` /
  `consumableType` / `toolType` and the sibling `baseItem`
- `system.damage.base` / `.versatile` as `DamageData`; `damage.parts` deleted
- `properties` as an array; the boolean map deleted
- `system.activities` on every rollable item; `actionType`, `attackBonus`,
  `formula`, `chatFlavor`, `critical`, `save`, `range`, `target`, `duration`,
  `uses` deleted from the item root
- spell activities — attack / save / heal / utility, with cantrip and upcast
  scaling
- `_stats` on every document
- version stamps: `SYSTEM_VERSION`, `dnd5e.systemMigrationVersion`,
  `_stats.systemVersion`, manifest `relationships.systems`

**Version truth cannot be staged.** Claiming 1.5.6 while emitting 5.x invites a
migration over documents with no legacy fields left to convert; claiming 5.3.3
while still emitting legacy fields strands them. Both corrupt, so the stamps move
in the same commit as the data.

**Gate:** no legacy field emitted anywhere · every rollable document has an
activity · printed damage totals unchanged across the invariant table.

**Outcome — measured, not asserted.** A real 65 MB Roll20 export
(*TotYP — The Sunless Citadel*) was converted and the emitted NeDB files read
back. Unit tests cannot see what the emitter actually wrote across a whole
campaign; this can.

| Measure | Before R2 | After R2 |
|---|--:|--:|
| Legacy fields in emitted items | 16 kinds | **0** |
| Items carrying `_stats.systemVersion` | 0 / 357 | **357 / 357** |
| Actors carrying `_stats.systemVersion` | 0 / 30 | **30 / 30** |
| Rollable items with an activity | 0 / 290 | **190 / 290** |
| Activated items with no activity | 140 | **0** |
| Weapons with dice in `damage.base` | 0 / 96 | **96 / 96** |
| Activity `_id` ≠ its map key | — | **0** |

The 100 items still without an activity all have `activation.type == ""` — they
are passive traits (*Keen Smell*, *Pack Tactics*, *Sunlight Sensitivity*), which
dnd5e also leaves activity-less. The check is not "everything has an activity"
but "nothing **activated** lacks one".

The first pass through that export is what found **B006–B010**: the unit suite
was 307-green while the converter was still emitting `system.scaling`,
`system.components`, `system.preparation`, `system.consume`, a flat `target`, a
legacy `uses` and `activation.cost` on every item. Those tests passed because
none of them looked at that half of the schema.

---

### R3 · 0.17.0 — Cleanup ✅

The documents *around* the ones R2 fixed. None of these carries damage, which is
why they survived R2 unnoticed — and why they are exactly the kind of thing a
suite that only tests the interesting path never looks at.

- **Class documents** — 5.x replaced `hitDice` / `hitDiceUsed` with the `hd`
  block. The old keys are not in `ClassData`, so every converted class arrived
  with the `d6` default whatever it really was. `saves` and `skills` were not in
  the schema either; `primaryAbility` and `properties` were missing.
- **Actor abilities** — `save` was emitted as a *number* where 5.x declares a
  `RollConfigField` object, and `mod` / `min` were carried even though dnd5e
  derives them. The derived values are still needed while translating attacks
  and DCs, so they now live in `_ability_derived` rather than being smuggled
  through the document.
- **Actor skills** — `bonuses.check` and `bonuses.passive` are `FormulaField`s in
  5.x, not numbers, and the block needs `roll`.
- **`source`** — a `SourceField` object in 5.x, a bare string in 1.5.6. It is on
  every item and every NPC, so the string form silently dropped attribution from
  every document the converter has ever produced.

**Gate:** suite green · `tools/verify_dnd5e.py` PASS on a real converted export.

---

### R4 · 1.0.0 — Acceptance ✅

Unit tests are necessary but **not sufficient**: a test on a Python dict cannot
detect that Foundry's storage layer dropped a field, which is exactly how the
damage loss above went unnoticed. So R4 ran a real export through a real Foundry
and measured the result three ways.

**The oracle.** Roll20 leaves the stat block's own text in each item's
description — *"Melee Weapon Attack +4 … Hit: 11 (2d8+2) piercing"*. That text
was written by the module's author, not by the converter, so comparing against it
cannot ratify a bug the way a test that recomputes the implementation's own logic
can. `tools/verify_dnd5e.py` now parses it and asserts that the to-hit and damage
dnd5e will actually roll equal the printed numbers.

That check found four defects that a 455-green suite and a clean schema check had
both passed: **B023**, **B024**, **B025** and **B026**. Every one of them produced
a document that loaded without a single error and rolled the wrong number.

**Results** — *TotYP: The Sunless Citadel*, 30 actors, 357 items:

| Check | Result |
|---|---|
| dnd5e migration triggered | **none** — `systemMigrationVersion` still 5.3.3 |
| documents rewritten by the migration | **0** (no `flags.dnd5e.persistSourceMigration`) |
| legacy fields surviving the load | **0** |
| weapons with dice in the **stored** `damage.base` | **96 / 96** |
| weapons with an attack activity | **96 / 96** |
| `_stats.systemVersion` intact after load | **387 / 387** |
| dice rolls evaluated in the live game | **62**, all finite |
| printed to-hit and damage vs. what dnd5e rolls | **61 checks, 0 wrong** |
| save spells with a DC · healing spells that heal | 12 · 2 |
| sentinels found | Bite, Shortsword, Dagger, Club, Shortbow |

The 96/96 stored-damage line is the one that matters most: it is the direct
negative control for M09, where a compat shim made the *live* document read
correctly while the *stored* one held nothing.

**Gate:** suite green · `tools/verify_dnd5e.py` PASS on emitted output ·
`tools/verify_persisted.mjs` PASS on the LevelDB Foundry wrote back · live rolls
match the printed stat blocks.

---

## Bugs

| ID | Found in | Summary | Fix |
|---|---|---|---|
| **B001** | R1 | `extractAbilityModifier()` dropped the flat addend on a symbolic formula. `"1d8 + @abilities.str.mod + 1"` returned `bonus=0`, so the printed total fell by 1 — a violation of the one invariant this port exists to protect. | **F001** |
| **B002** | R1 | `attackActivity()` rejected only `ability="none"`. `"STR"`, `"strength"`, `"banana"` passed through and produced an activity dnd5e validates away just as silently. | **F002** |
| **B003** | R1 → R2 | `Items.createItemInventory()` routes `inventory_type == "consumable"` to `createItemWeapon()`, producing an item whose declared type and system shape disagree. | **F003** |
| **B004** | R1 → R2 | `actors.py` reads the legacy `["system"]["weaponType"]` from compendium items at lines 1799, 2034, 2134. Breaks against a 5.x compendium. | **F004** |
| **B005** | R1 | `attack.flat` does not suppress `@mod` in damage — it only makes the *attack roll* a flat bonus. The extractor used it to "preserve" an unmatched bonus, which instead inflated damage by the ability modifier. | **F005** |
| **B006** | R2 | Spells emitted `system.scaling`, `system.components`, `system.preparation` and `system.consume`. None exists in 5.3.3 `SpellData`. Foundry drops unknown keys silently, so every spell lost its components, its prepared state and all upcast scaling — with no error anywhere. | **F006** |
| **B007** | R2 | An item with an activation but nothing rollable got **no activity**, so it had no button on the sheet at all. dnd5e's own migration gives these a `utility` activity (`ActivitiesTemplate.#createInitialActivity`). Measured: 26 spells and 114 features. | **F007** |
| **B008** | R2 | `Item.createItemFromHandout()` builds its entity dict by hand and never called `documentStats()`, so 10 handout-derived items shipped with no `_stats` — exactly the documents dnd5e would then migrate. | **F008** |
| **B009** | R2 | The whole shared activated-effect template was still 1.5.6-shaped on **every** item type: `activation.cost` (5.x reads `value`), `range.long`, the flat `target`, and `uses {value, max, per}` (5.x stores `spent` and a `recovery` array). Also `ItemActivation.NONE`/`SPECIAL` and `ItemRange.NONE` are not valid 5.x enum values and reset their field on load. | **F009** |
| **B010** | R2 | `_buildActivities()` built the heal activity as `healActivity(activity_id)` — without its healing formula. Every healing spell healed nothing. *Cure Wounds* shipped with `healing: {}`. | **F010** |
| **B011** | R2 | The unit suite was 307-green across all of B006–B010. The tests asserted the shapes the emitter produced for weapons and never looked at the activated-effect or spell half of the schema, so a whole family of legacy output was invisible to them. | **F011** |
| **B012** | R2 | `ACTIVATION_TYPES` was read off a truncated grep of `config.mjs` and lost `crew` and `special`. A "special" activation therefore became blank. Measuring with a tool that silently truncates is the same class of error as not measuring. | **F012** |
| **B013** | R2 | `activation` / `range` / `duration` / `target` were emitted at the document root for **every** item type. Only `SpellData` declares them; `WeaponData`, `FeatData`, `EquipmentData` and `ConsumableData` do not, so Foundry dropped them and each activity kept its defaults — every reaction became an action, every ranged attack read "self", every target vanished. | **F013** |
| **B014** | R2 | `WeaponData` declares its own `range {value, long, reach, units}` with *numeric* fields rather than reusing the shared `RangeField`. Weapons got the shared shape, which loses `reach` and `long` and puts a formula string into a `NumberField`. | **F014** |
| **B015** | R2 | Cantrip save damage was written as `onSave: "half"`. dnd5e sets `"none"` in `SaveActivityData#_preCreate` — but only when the key is absent, and the converter always writes one. | **F015** |
| **B016** | R2 | `createItemFromCompendium()` replaces the whole entity with the compendium copy *after* the constructor stamped `_stats`, so those items carried whatever version their pack was built with — and would be migrated. | **F016** |
| **B017** | R2 | `ItemFeatRecharge.getDict()` returned a complete `uses` block that overwrote the one from `ItemActivation`, so a feature with both a charge count and a recharge ("2/day, Recharge 5-6") lost the charge count. | **F017** |
| **B018** | R2 | Save activities emitted `save.dc.value` and `damage.critical`. Neither is in the 5.3.3 `SaveActivityData` schema; both are dropped on load, leaving the stored document non-native. | **F018** |
| **B019** | R3 | `ItemClass` emitted `hitDice` and `hitDiceUsed`. 5.x replaced both with `hd = {additional, denomination, spent}`, so every converted class arrived at the `d6` default whatever its real hit die was — a Barbarian included. `saves` and `skills` were emitted too and are not in `ClassData`. | **F019** |
| **B020** | R3 | Actor `abilities.<key>.save` was a **number** where 5.x declares a `RollConfigField` object, and `mod` / `min` were emitted despite being derived. Seven places in `actors.py` read those derived values back out of the emitted document. | **F020** |
| **B021** | R3 | `system.source` was a bare string. 5.x uses a `SourceField` object, so the string is dropped and every item and NPC the converter has ever produced loses its attribution. | **F021** |
| **B022** | R3 | Actor `skills.<key>.bonuses.check` / `.passive` were numbers where 5.x declares `FormulaField`s, and the block was missing `roll`. `mod` was emitted despite being derived. | **F022** |
| **B023** | R4 | Not every Roll20 sheet carries `<ability>_mod`; the Sunless Citadel export has full ability *scores* and none at all. Defaulting the modifier to 0 left the emitted document correct — dnd5e derives `mod` from the score — while every *internal* decision that depends on the modifier went wrong. A Bugbear with STR 15 and a printed +4 failed the `mod + prof == tohit` match, so the converter recorded "STR, +4 bonus" and dnd5e rolled **+8**; and the +2 baked into `2d8+2` was never recognised as the ability modifier, so dnd5e appended it again as **2d8+4**. | **F023** |
| **B024** | R4 | When no ability reproduced the printed to-hit, the fallback set `bonus = tohit − str_mod` and forgot that dnd5e also adds proficiency. Every such attack overshot by the proficiency bonus — a Goblin's printed +5 rolled +7. | **F024** |
| **B025** | R4 | `actors.py` picks the attack ability by matching the printed to-hit, then `extractAbilityModifier()` independently picked a *different* ability to drive the damage residual to zero. The caller kept its own ability and the extractor's bonus, so the damage was wrong by the difference between the two modifiers: a Goblin's printed `1d6+2` became `1d6−1`. | **F025** |
| **B026** | R4 | `getProficiencyBonus()` computed `int(ceil(cr + 7) / 4)` — the division sits *outside* the ceiling, which yields **+1** at CR 0. Every CR 0–4 creature has +2, and dnd5e clamps to it, so every to-hit derived for a CR 0 creature was off by one. | **F026** |

### B001 in detail

The bug was in the implementation, but the reason it survived was in the **test**:

```py
expected = bonus if not symbolic else mods.get(symbolic, 0)   # wrong
```

That discards the flat bonus whenever the formula named an ability, so the
invariant check ratified the broken implementation. The test was tautological in
exactly the case it most needed to be independent.

### B005 in detail

`ModifierExtraction.flat` was designed to mean "do not add `@mod`". Reading
dnd5e 5.3.3 rather than assuming shows it means no such thing:

```js
// attack-data.mjs:261 — getAttackData()
if ( this.attack.flat ) return CONFIG.Dice.BasicRoll.constructParts({ toHit: this.attack.bonus }, rollData);
```

`attack.flat` replaces the whole **attack roll** with a flat bonus. Damage is
governed separately, in `_processDamagePart`:

```js
// attack-data.mjs:387-392
if ( this.item.type === "weapon" ) {
  const isDeterministic = new Roll(roll.parts[0]).isDeterministic;
  const includeMod = ... && !isDeterministic && ...;
  if ( includeMod && !roll.parts.some(p => p.includes("@mod")) ) roll.parts.push("@mod");
}
```

So `@mod` is appended when — and only when — the item is a **weapon** and its
base damage part **rolls dice**. Setting `flat` would have left the bonus in the
damage *and* still had `@mod` added on top: the exact double-count the port
exists to prevent, inflating every unmatched-bonus weapon.

Two corrections followed:

- **The general rule is subtraction**, not suppression: `residual = printed −
  mod(ability)` preserves the total for *any* ability. Matching the ability to
  the baked bonus is a refinement that drives the residual to zero, which is what
  an SRD statblock looks like — not a precondition for correctness.
- **Spells, feats and flat damage must be left alone.** Nothing appends `@mod`
  to them, so subtracting anything reduces the printed damage.
  `appendsAbilityModifier(is_weapon, has_dice)` now encodes the system's actual
  rule, and the invariant is asserted in both directions.

## Fixes

| ID | Closes | Change |
|---|---|---|
| **F001** | B001 | Symbolic branch preserves the flat addend and lower-cases the ability key (`ABILITY_MOD_RE` matches case-insensitively). Invariant test corrected to `bonus + mods[symbolic]`. Fixtures INV-16 / INV-17 added, plus a non-vacuity assertion requiring a symbolic-*and*-flat row. |
| **F002** | B002 | `attackActivity()` and `extractAbilityModifier()` validate the ability against `ABILITIES`. Empty stays legal — it means "no modifier", unlike `"none"`. |
| **F005** | B005 | `appendsAbilityModifier(is_weapon, has_dice)` encodes dnd5e's real rule. The extractor subtracts instead of going flat, and leaves spell / feat / flat damage untouched. `ModifierExtraction.flat` is now always `False` and documented as an attack-roll concern. New invariant test asserts the total in the no-auto-modifier direction too. |
| **F003** | B003 | `createItemInventory()` routes consumables to `createItemConsumable()`. The `specific` argument is only forwarded when it really is an `ItemConsumable`, so a mis-typed caller cannot splice weapon keys into a consumable. |
| **F004** | B004 | `_compendiumWeaponType()` reads `system.type.value` first and falls back to `system.weaponType`, so the converter works against a 1.x **or** a 5.x SRD compendium. |
| **F006** | B006 | `ItemSpellComponents.getDict()` emits the 5.x `properties` set; `ItemSpellPreparation.getDict()` emits `method` + numeric `prepared` via `dnd5e.spellPreparation()`; `ItemSpellScaling.getDict()` and `ItemConsume.getDict()` return `{}` and the scaling object is passed to `_buildActivities()` instead, where `dnd5e.damageScaling()` reproduces `BaseActivityData.transformDamagePartData` — including the rule that a scaling die matching the damage die becomes a die *count* rather than a formula. |
| **F007** | B007 | `_utilityOnly()` emits a `utility` activity whenever an item has a real `activation.type` and nothing rollable. `createStandardData()` now builds activities when there is an activation even with no attack. Passive traits, which have no activation, still correctly get nothing. |
| **F008** | B008 | `createItemFromHandout()` calls `documentStats()` and also emits the `effects` array it was missing. |
| **F009** | B009 | `dnd5e.activationData` / `rangeData` / `durationData` / `targetData` / `usesData` / `usesFromLegacy` / `recovery` build the 5.3.3 shapes, read from `module/data/shared/*-field.mjs`. Every enum is validated against a whitelist (`ACTIVATION_TYPES`, `RANGE_UNITS`, `DURATION_UNITS`, `AREA_TARGET_TYPES`, `INDIVIDUAL_TARGET_TYPES`, `RECOVERY_PERIODS`) — an unrecognised value resolves to the sane default rather than silently resetting the field on load. `ItemFeatRecharge` now emits a `uses.recovery` rule, since `system.recharge` no longer exists. |
| **F010** | B010 | The heal activity is built from the first damage part, re-typed as `healing`. |
| **F011** | B011 | `tests/test_dnd5e_template.py` — 122 tests covering the activated-effect template, the spell fields, damage scaling, utility and heal activities, each asserting **absence** of the legacy key as well as presence of the replacement. Plus `verify.py`, which reads the emitted NeDB files of a real converted campaign; that is what found the family in the first place, and R4 makes it a gate. |
| **F012** | B012 | `crew` and `special` restored. The test that exercises the whitelist now lists the sixteen values literally, copied from `config.mjs`, instead of iterating `ACTIVATION_TYPES` — which could only ever agree with itself. |
| **F013** | B013 | `dnd5e.ROOT_ACTIVATED_TYPES` names the one item type that keeps the block at the root. `createStandardData()` emits it there for spells and only `uses` elsewhere; `_applyMetadata()` copies activation, range, duration and target onto every activity, with `override` set for the types that have no root copy to inherit from. This mirrors `BaseActivityData.createInitialActivity`, which does the same during migration. |
| **F014** | B014 | `dnd5e.weaponRange()` builds the weapon-specific numeric shape; `createItemWeapon()` uses it and the shared range is no longer written for weapons. |
| **F015** | B015 | `_buildActivities()` takes the spell level and passes `on_save="none"` for a level-0 spell. |
| **F016** | B016 | `createItemFromCompendium()` restamps `_stats` after the copy. |
| **F017** | B017 | `_mergeRecharge()` appends the recharge rule to the existing `recovery` list and keeps the charge maximum, replacing the block only when there is nothing to preserve. |
| **F018** | B018 | `saveActivity()` emits `save.dc = {calculation, formula}` and `damage = {onSave, parts}`. The two tests that asserted `dc.value` were themselves ratifying the defect and now assert its absence. |
| **F019** | B019 | `ItemClass.getDict()` emits `hd`, `primaryAbility` and `properties`, and drops `saves` / `skills`. `CLASS_PRIMARY_ABILITY` is an explicit PHB table rather than a guess from the spellcasting ability — a Fighter has a primary ability and no spellcasting, and a Paladin's primary abilities are STR *and* CHA. A regression test asserts the hit die of all twelve PHB classes against the book, not against the implementation's own table. |
| **F020** | B020 | `createActorAbilities()` caches `mod` and the save bonus in `_ability_derived` and emits the 5.x shape. The seven readers now call `abilityDerived()`. |
| **F021** | B021 | `dnd5e.sourceData()` builds the `SourceField` object; the Roll20 free-text maps onto `custom`, which is what dnd5e displays when `book` is unset. |
| **F022** | B022 | Skill bonuses are emitted as formula strings, `roll` is present, and the derived `mod` is gone. |
| **F023** | B023 | `Actor.abilityModifier()` reads `<ability>_mod` with a sentinel default and falls back to `floor((score − 10) / 2)` when the sheet has none. Every internal modifier read — save bonuses, initiative, skills, the to-hit match and the damage extraction — goes through it. |
| **F024** | B024 | The fallback subtracts the proficiency bonus the weapon is about to be marked with, so `mod + prof + bonus` reproduces the printed to-hit. |
| **F025** | B025 | `extractAbilityModifier()` takes a `required` ability. When the caller has already committed to one, the residual is measured against *that* modifier and no other. Without a `required` the matching search still runs, so the SRD-shaped zero-residual case is unchanged. |
| **F026** | B026 | `max(2, floor((cr − 1) / 4) + 2)`, verified against the Monster Manual's own table at all 34 challenge ratings — plus a non-vacuity assertion that the old formula would have failed that table. |
| **F027** | B027 | The two `del`s for `saves` / `skills` are gone — F019 removed those keys from `ItemClass` but not their deletion sites — and `spellcasting` is dropped with `pop(..., None)` so a future schema change degrades instead of crashing. |
| **F028** | B028 | `dnd5e.weightData()` / `priceData()` build the `{value, units}` and `{value, denomination}` objects `PhysicalItemTemplate` declares, and `dnd5e.attunement()` maps the 1.5.6 numeric enum onto the 5.x string. A bare number does not fail loudly; `SchemaField` resets the field, which is why every converted item silently lost its weight and price. |
| **F031** | B031 | `warnIfLevelDBPacks()` detects the LevelDB pack directories systems have shipped since Foundry v11 and reports the one real cause, naming what the user loses, instead of five generic per-file failures. **Reading** LevelDB is not addressed: ADR-003 rejected a native LevelDB dependency for the cx_Freeze build, and that reasoning still holds. Compendium enrichment remains unavailable on current installs — now legibly rather than silently. |
| **F032** | B032 | Token bars point at `attributes.hp`, the one path the 5.x actor schema declares, and the ActorDelta carries `attributes.hp` instead of the synthetic `bar1`. The undeclared `attributes.bar1` / `bar2` blocks are no longer emitted on the actor. Roll20 tokens carry HP in the first bar, so this is the `--force-hp-for-token-bar1` behaviour made the default; a genuinely custom second bar has no representable target and is left unset rather than pointed at a field that renders empty. |
| **F033** | B033 | `dnd5e.armorDexLimit()` returns `None` for light armour, 2 for medium and 0 for heavy — `dex` is nullable, so `None` and `0` are different statements and emitting 0 everywhere capped every converted armour at +0. `stealth` becomes the `stealthDisadvantage` property, the `speed` block is dropped, and `ItemObject.getDict()` returns `{}` so weapons stop claiming AC 10 and an `hp` block. |
| **F034** | B034 | `createDetailXP()` keeps the slash-format value it parses instead of overwriting it with 0 on the next line, no longer shadows the `max` builtin, and emits only `value` — 5.x derives `min`, `max` and `pct`. |
| **F035** | B035 | `hlbonus = ""` — it was `==`, a no-op comparison, so a spell with `spellhlbonus = 0` got `" + 0"` scaling and a scaling mode it should not have. |
| **F037** | B037 | `createActorTools()` emits `system.tools` directly, using the same keys and the same `{value: 1, ability: "int", bonuses: {check: ""}}` entry dnd5e's `#migrateToolData` shim writes at load time — replicating the migration at creation time rather than depending on it, per ADR-008. `traits.toolProf` is no longer emitted, and a tool name with no dnd5e key is logged instead of vanishing into a `custom` string the schema drops. |
| **F038** | B038 | The Shaped skill branch routes through the 5.x shape F022 introduced (`bonuses.check`/`passive` formulas plus `roll`), the inverted bonus sign is corrected to match the standard branch, the chained `passive = mod = …` that overwrote the modifier is split, and a skill whose name has no dnd5e key is logged rather than written to a key `skills` deletes on load. |
| **F029** | B029 | The activity carries a `consumption.targets` entry of type `itemUses` instead of a deep copy of the item's `uses`. `ActivitiesTemplate` puts the pool on the item root, so the copy was a second pool rendered beside the real one — and with no target, activating a limited-use item spent nothing. |
| **F030** | B030 | `spells.spellN` emits the declared `{value, override}` and drops `spell0`; NPCs get `override` from the sheet's printed slot counts, characters keep `None` so class progression stays in charge. `attributes.spell.level` is parsed from the Spellcasting trait and emitted natively; `details.spellLevel`, `attributes.spelldc` and `attributes.spellLevel` are gone. The bug report's claim that a `max(cr, 1)` fallback existed to be defeated was wrong — `spell.level` is `nullable: false, initial: 0`, so it is always numeric and the fallback cannot fire; see the correction in the bug doc. |
| **F036** | B036 | `Actor.parseInnateUses()` reads `(\d+)\s*/\s*(day\|short\|long)`. Under `(\d)` an annotation of "10/day" matched the leading `1` and the period group then failed against the `0`, so the spell arrived with one use and no recovery rule. |
| **F039** | B039 | `RECOVERY_PERIODS` matches `CONFIG.DND5E.limitedUsePeriods` plus `recharge`. `charges` is a *consumption* type in 5.x, not a recovery period, and `period` is an unvalidated `StringField` — so the legacy value was stored and then silently ignored. It now degrades to no recovery rule. |
| **F040** | B040 | Containers emit `type: "container"` and the declared `capacity` (`count` / `weight`), with `weightless` moved into `properties` and `quantity` pinned to 1. The translation is the one dnd5e's own `#migrateCapacity` performs; emitting `backpack` set `persistSourceMigration`, queueing every container for a rewrite. |
| **F041** | B041 | `dnd5e.creatureType()` splits the Roll20 phrase into `{value, subtype, swarm, custom}`, validating the head word against `CONFIG.DND5E.creatureTypes` and routing anything unrecognised to `custom`. `CreatureTypeField.value` has no `choices`, so "humanoid (goblinoid)" was stored happily and then matched nothing that looked it up. |
| **F042** | B042 | CSS shorthand repeats each nibble (`#abc` ≡ `#aabbcc`), so the expansion is `×17`, not `×16`; the 4-digit `#rgba` form drops the alpha nibble rather than misreading it as blue. |
| **B043** | — | Not a fix: the Foundry 14 gap is filed as a documented limitation. The output deliberately declares core 13, because `DOCUMENT_SCHEMA_CORE_VERSION` is what makes Foundry run the NeDB→LevelDB migration the output depends on. Emitting v14 natively needs the LevelDB dependency ADR-003 rejected — the same blocker as B031. |


## Per-step cycle

```
Architect  — restate the slice; name the invariant it must not break
Senior Dev — implement; DELETE legacy fields inside the switch, never before
QA         — cases first, then the full suite
Rubber duck— independent review of the diff
Gate       — suite green · no legacy field · version bumped · changelog · ADR if
             the decision is non-obvious
Commit     — annotated, pushed, one per step
```

## Known defect classes (regression targets)

| | Defect | Covered by |
|---|---|---|
| D1 | damage double-count — `@mod` appended on top of a baked-in bonus | INV-01…17 |
| D2 | three modifier encodings: numeric, symbolic `@abilities.str.mod`, custom formula | INV table + B001 regression |
| D3 | `attack.ability="none"` readable but not writable — activity silently not created | `testAbilityNoneIsRejected` |
| D4 | stored ≠ live: migration dropped `damage.base` while a shim faked it in memory | R4 stored-document assertions |
| D5 | degenerate damage: `1d0` nets, flat `1` torches, `1d1` | `TestParseDamageFormula` |
| D6 | dirty damage types: `"bludgeoning "`, `"spell"`, `"bludgeoning or slashing"` | `TestDamageType` |

## Out of scope

Non-dnd5e systems · re-authoring the Roll20 statblock parser · Foundry v14 ·
reading LevelDB SRD compendiums.
