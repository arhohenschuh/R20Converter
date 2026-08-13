# Architecture Decision Records

This directory records the significant architectural and technical decisions made
for R20Converter, using lightweight [ADRs](https://adr.github.io/).

Each ADR captures a single decision: the context that forced it, the decision
itself, the alternatives that were rejected, and the consequences we accept.
ADRs are immutable once accepted — if a decision changes, a **new** ADR is added
that supersedes the old one, and the old one is marked `Superseded by ADR-XXX`.

Code that exists because of a decision recorded here should carry a short comment
referencing the ADR number, so the "why" is discoverable from the code.

## Index

| ADR | Title | Status |
| --- | ----- | ------ |
| [ADR-001](ADR-001-build-reproducibility.md) | Reproducible builds and visible errors | Accepted |
| [ADR-002](ADR-002-target-foundry-v13.md) | Target Foundry VTT v13+ and centralize version constants | Accepted |
| [ADR-003](ADR-003-leveldb-pack-format.md) | Emit LevelDB world/pack data via the Foundry CLI | Accepted |
| [ADR-004](ADR-004-testing-and-ci.md) | Automated test suite and CI safety net | Accepted |
| [ADR-005](ADR-005-table-result-schema.md) | Emit the Foundry v13 `TableResult` schema | Accepted |
| [ADR-006](ADR-006-dnd5e-subclass-documents.md) | Emit dnd5e subclasses as documents, not a string field | Accepted |
| [ADR-007](ADR-007-dnd5e-species-background-documents.md) | Emit dnd5e species and backgrounds as documents, not string fields | Accepted |
| [ADR-008](ADR-008-emit-dnd5e-5x-natively.md) | Emit dnd5e 5.x documents natively | Accepted |
| [ADR-009](ADR-009-leveldb-module-packs.md) | Write LevelDB compendium packs for modules | Accepted |
| [ADR-010](ADR-010-module-pack-folders.md) | Preserve the Roll20 folder hierarchy in module compendium packs | Accepted |
| [ADR-011](ADR-011-scene-folder-manifest.md) | Scene folders come from an explicit manifest, never inference | Accepted |

## Numbering

ADRs are numbered sequentially in the order they are accepted. The file name is
`ADR-<number>-<kebab-case-title>.md`.
