# ADR-013: Selectable dnd5e output target, defaulting to 6.x

- **Status**: Accepted
- **Date**: 2026-11-06
- **Supersedes**: [ADR-008](ADR-008-emit-dnd5e-5x-natively.md) (single dnd5e 5.x target)
- **Superseded by**: -

## Context

ADR-008 made the converter write dnd5e 5.x documents natively and stamp them `5.3.3`, so the
system did not migrate them. Live campaigns now run dnd5e 6.0.6 on Foundry 14.369. dnd5e 6
raised `needsMigrationVersion` to `6.0.0` and reads most 5.x fields only through data-model
shims scheduled for removal in 7.0. A persisted world migration updates only diffs. Data-model
migration is in-memory only, so a 5.x document loaded in 6.x stays 5.x in storage indefinitely.

A native 6.0.6 replay of a real export confirmed the stored-source differences: AC `calc`/`formula`
to `calcs`/`formulas`/`override`; ability, skill, tool, initiative, and global bonuses to `roll`/
`rolls` fields; flat movement keys to `movement.speeds`; physical `rarity` to `rarities`;
small-creature token `lockScale`; and effect change IDs, `magical`, and `system.origin`. It also
exposed B127, a doubled initiative bonus that only the 6.x migration produces.

Some installations still run dnd5e 5.3.3, and a 6.x document is unreadable there.

## Decision

The converter writes exactly one dnd5e generation per run, selected by `--dnd5e-version`
(GUI: **D&D 5e system version**):

| Target | Stamped version | Manifest `minimum` | Default |
| --- | --- | --- | --- |
| `6.x` | `6.0.6` | `6.0.0` | yes |
| `5.3.3` | `5.3.3` | `5.0.0` | no |

`src/dnd5e.py` remains the single source of version constants. Builders keep producing the
validated 5.x shape. For the 6.x target, `R20Converter.finalizeSystemDocuments` rewrites actors,
items, card items, and scene tokens into the 6.0 persisted shape before world save or module
assembly. That keeps packs and the Adventure snapshot identical. The rewrite mirrors dnd5e 6.0.6
`_migrateArmorClass`, `#migrateBonusData`, `MovementField._migrate`, `_migrateInitiative`, the
version-gated effect migrations, and small-token `lockScale`. Effect change IDs are deterministic.
Effects already stamped for dnd5e 6 are left untouched.

The converter warns when the installed dnd5e system or a donor compendium is newer than the
selected target. It never down-converts donor content.

## Consequences

- Default output loads in dnd5e 6.0.6 with no persisted system migration. Its stored source is a
  fixed point of the native data model for every migrated field.
- `5.3.3` output is unchanged except for generic defect fixes that apply to both targets.
- A 7.x release will require a new target and fresh native-source evidence. Adding a version
  string alone is not sufficient.
- Worlds and modules record the selected version in `systemVersion`,
  `dnd5e.systemMigrationVersion`, every document `_stats.systemVersion`, and
  `relationships.systems`.
