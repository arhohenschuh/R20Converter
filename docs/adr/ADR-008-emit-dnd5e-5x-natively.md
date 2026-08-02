# ADR-008: Emit dnd5e 5.x documents natively

- **Status**: Accepted
- **Date**: 2026-08-02
- **Supersedes**: —
- **Superseded by**: —
- **Relates to**: [ADR-002](ADR-002-target-foundry-v13.md) (Foundry core schema)

## Context

ADR-002 ported the **Foundry core** document schema to v13. It did not touch the
**dnd5e system** schema, and `src/foundry.py` still declares:

```py
DEFAULT_SYSTEM_VERSION = "1.5.6"
```

Every item R20Converter emits therefore uses dnd5e ~1.5.6 shapes. dnd5e has since
restructured, not merely renamed, most of them:

| Emitted (1.5.6) | dnd5e 5.x |
|---|---|
| `system.weaponType` | `system.type.value` |
| `system.baseItem` | `system.type.baseItem` |
| `system.armor.type`, `consumableType`, `toolType` | `system.type.value` |
| `system.damage.parts: [[formula, type], …]` | `system.damage.base`: a `DamageData` object |
| `system.properties: {amm: false, hvy: true, …}` | `properties: ["hvy"]` — an array |
| `actionType`, `attackBonus`, `formula`, `chatFlavor`, `critical`, `save`, `range`, `target`, `duration`, `uses` | inside `system.activities` |
| *(nothing)* | `system.activities` — the Activities system |
| *(nothing)* | `_stats` |

The same reasoning as ADR-002 applies, but the conclusion is stronger. ADR-002 could
observe that Foundry's v9→v10 migrations were *deleted*, so old documents simply do not
load. dnd5e's migrations still exist — which is worse, because they run, report success,
and corrupt.

Three findings drove this ADR. All were measured while repairing two converted 760 MB
modules by hand, not inferred:

**1. The dnd5e migration never gives weapons an attack.** dnd5e builds a weapon's default
attack in `WeaponData#_preCreate`. That hook fires on document **creation**; a migration is
an **update**, so it never runs. Measured on two converted modules: 479/479 and 742/742
spells migrated with working activities, while **393/393 and 524/524 weapons migrated with
zero** — every weapon unrollable.

**2. The migration can silently destroy damage.** `migrateCompendium()` consumes the legacy
`system.damage.parts` array and stamps `_stats.systemVersion = 5.3.3`, but for a subset of
documents writes an **empty** `system.damage.base` back to the pack. A compatibility shim
reconstructs the base in memory from `parts`, so the *live* document reads correctly while
the *stored* document holds nothing — and once the version stamp changes, the shim stops
running and the dice are unrecoverable. Measured: 390 weapons with dice live, **293**
stored. Roughly 100 weapons per module lost all damage.

**3. Roll20 bakes the ability modifier into the damage.** dnd5e always appends `@mod`,
resolved from the activity's ability. Roll20 writes `"Bite 1d10+2"` where the SRD writes
`"1d10"` plus the modifier. Attaching a default activity without compensating rolls
`1d10+2+mod`.

Repairing this after the fact costs a live Foundry session, a GM login, and a bespoke
script per module — and every one of the traps above lives in that path.

## Decision

**R20Converter emits dnd5e 5.x documents natively.** Concretely:

1. A new `src/dnd5e.py` is the single source of truth for every dnd5e version number and
   data shape, mirroring the role `foundry.py` plays for the core schema. Its constants are
   read out of the dnd5e 5.3.3 source — `module/config.mjs`,
   `module/data/shared/damage-field.mjs`, `module/documents/activity/attack.mjs` — not
   inferred from documentation.

2. **Activities are built by the converter, at document creation time.** This is the crux.
   We are *creating* documents, so the `_preCreate` gap that strands migrated weapons
   cannot occur in our output.

3. **The baked-in ability modifier moves into the activity, never stays in the damage.**
   The invariant is that the *printed damage total is unchanged*:

   ```
   bonus == result.bonus + (0 if result.flat else mods[result.ability])
   ```

   The ability is chosen as the one whose modifier **equals** the baked bonus — the data
   reveals which ability the Roll20 sheet used. Two cases need an explicit rule:

   - **No ability matches** (a magic weapon, or a statblock quirk): do **not** subtract.
     Keep the bonus in the damage and set `attack.flat = true` so `@mod` is not added.
     Subtracting an unmatched value would change the printed damage.
   - **Two abilities tie**: resolve in the fixed order `str, dex, con, int, wis, cha`.
     Determinism matters — the converter must produce byte-identical output for the same
     input, or a diff between two builds means nothing.

4. **Version truth is atomic with schema truth.** `SYSTEM_VERSION`,
   `dnd5e.systemMigrationVersion`, each document's `_stats.systemVersion`, and the manifest
   `relationships.systems` entry all change in the **same commit** as the documents. See
   Consequences for why this cannot be staged.

5. **`baseItem` is resolved from an explicit table, never inferred.** Unmapped names yield
   `""`, which is legal. A wrong slug is worse than none: dnd5e would apply the wrong
   properties, mastery and proficiency.

6. **`attack.ability = "none"` is never written.** It *reads* back as `null`, and is
   correctly documented as making `@mod` resolve to 0 — verified with a probe actor. But
   writing it fails schema validation and the activity is then **silently not created**.
   `dnd5e.attackActivity()` raises on it; suppress the modifier with `flat=True` instead.

## Alternatives considered

- **Keep emitting 1.5.6 and let dnd5e migrate.** Rejected — this is today's behaviour, and
  the three findings above are what it produces. Unlike ADR-002's case, the migration is
  not merely absent: it runs, reports success, and leaves weapons unrollable and ~100
  weapons per module without damage.

- **Post-process the packs after conversion.** Rejected. This is the current workaround. It
  requires a live Foundry session and a GM login, it is where every trap lives, and it has
  to be redone for every module. It also cannot fix the `_preCreate` gap at the source — it
  can only paper over it.

- **Stage the port across several minor releases** (types, then damage, then properties,
  then activities). **Rejected after review** — this was the original plan. Removing
  `damage.parts` before `activities` exist leaves damage with nowhere rollable to live, and
  any intermediate release emits documents that are neither old enough for dnd5e's migrator
  nor complete enough for 5.x: strictly worse than today. The port ships as one atomic
  switch. Preparatory work that does **not** change output may land earlier.

- **Support both 1.5.6 and 5.x behind a flag.** Rejected, for ADR-002's reasons: it doubles
  the surface area of the least-tested part of the codebase to serve a system generation
  several years old. An internal flag during development is fine; shipped output has one
  shape.

## Consequences

- Converted worlds load in Foundry v13+ with dnd5e 5.x and **need no migration** — which is
  the point, because the migration is what breaks them.
- Output is **no longer usable on dnd5e below 5.0.0**. Breaking change; must be called out
  in the README and changelog.
- **The version claim cannot be staged.** Claiming 1.5.6 while emitting 5.x invites a
  migration over documents with no legacy fields left to convert — precisely finding (2).
  Claiming 5.3.3 while still emitting legacy fields strands them, because the migration
  that would have converted them is skipped. Both directions corrupt, so the stamps move
  with the data.
- **Unit tests are necessary but not sufficient.** A test on a Python dict cannot detect
  that Foundry's storage layer dropped a field — that is exactly how finding (2) went
  unnoticed. An end-to-end gate that imports into a clean world, **reloads**, and inspects
  the *persisted* document is required before this is called done.
- The tar pit is the boundary between `items.py` and `actors.py`. `items.py` currently
  serialises items locally, but choosing the attack ability needs actor ability modifiers,
  the formula's shape, and whether the source is an NPC action, a PC action or a spell —
  context that only exists in `actors.py`. Changing `getDict()` alone produces well-formed
  JSON that rolls wrong.
- Spells need their own activity builders. They are not weapons with damage: they carry
  attack/save/heal/utility variants, cantrip and upcast scaling, and slot consumption, and
  `addSpells()` already parses them separately.
