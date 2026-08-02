# Roadmap — dnd5e 5.x native output

**Goal:** R20Converter emits documents that Foundry **v13+** and dnd5e **5.x** load
with **zero migration**.

Decision record: [ADR-008](docs/adr/ADR-008-emit-dnd5e-5x-natively.md).

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
| **R2** | 0.16.0 | The Switch — atomic dnd5e 5.x emission | Yes, breaking | Next |
| **R3** | 0.17.0 | Cleanup — routing bug, compendium reads, origin docs | Yes | Planned |
| **R4** | 1.0.0 | Acceptance — real exports through a real Foundry | No | Planned |

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

### R2 · 0.16.0 — The Switch (next)

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

---

### R3 · 0.17.0 — Cleanup

- **B003** — `Items.createItemInventory()` routes `inventory_type == "consumable"`
  to `createItemWeapon()`
- **B004** — `actors.py` reads `compendium_item.entity["system"]["weaponType"]`
  (lines 1799, 2034, 2134); breaks against a 5.x compendium
- Validate class / subclass / species / background documents (ADR-006, ADR-007)
  against dnd5e 5.3.3 — claiming 5.3.3 means their migrations are skipped too

---

### R4 · 1.0.0 — Acceptance

Unit tests are necessary but **not sufficient**: a test on a Python dict cannot
detect that Foundry's storage layer dropped a field, which is exactly how the
damage loss above went unnoticed.

- Convert real *Dragons of Icespire Peak* and *Out of the Abyss* exports
- Import into a clean Foundry v13 + dnd5e 5.3.3 world
- **Zero migrations triggered**, zero validation errors
- Reload, then read the **persisted** documents — not the live accessors
- Roll a representative PC weapon, NPC weapon, attack spell, save spell, healing
  spell and consumable
- **Non-vacuity guards:** actor / item / weapon counts > 0, and named sentinels
  found after import — *Bite, Longsword, Fire Bolt, Net, Torch*. A suite that
  scans zero documents and reports PASS is worse than no suite.

---

## Bugs

| ID | Found in | Summary | Fix |
|---|---|---|---|
| **B001** | R1 | `extractAbilityModifier()` dropped the flat addend on a symbolic formula. `"1d8 + @abilities.str.mod + 1"` returned `bonus=0`, so the printed total fell by 1 — a violation of the one invariant this port exists to protect. | **F001** |
| **B002** | R1 | `attackActivity()` rejected only `ability="none"`. `"STR"`, `"strength"`, `"banana"` passed through and produced an activity dnd5e validates away just as silently. | **F002** |
| **B003** | R1 (open) | `Items.createItemInventory()` routes `inventory_type == "consumable"` to `createItemWeapon()`. Pre-existing; scheduled for R3. | — |
| **B004** | R1 (open) | `actors.py` reads the legacy `["system"]["weaponType"]` from compendium items at lines 1799, 2034, 2134. Breaks against a 5.x compendium. Scheduled for R3. | — |
| **B005** | R1 | `attack.flat` does not suppress `@mod` in damage — it only makes the *attack roll* a flat bonus. The extractor used it to "preserve" an unmatched bonus, which instead inflated damage by the ability modifier. | **F005** |

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
