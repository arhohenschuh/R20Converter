# ADR-003: Keep writing NeDB files, defer LevelDB emission

- **Status**: Accepted
- **Date**: 2026-07-25
- **Supersedes**: —
- **Superseded by**: —

## Context

Since Foundry v11, world data and compendium packs are stored as **LevelDB
directories**, not the newline-delimited-JSON **NeDB `.db` files** that
R20Converter writes. A v13 world directory contains `actors/`, `scenes/`,
`journal/`, `items/` and friends as LevelDB directories full of opaque binary
files (`CURRENT`, `LOCK`, `MANIFEST-000001`, `000001.log`).

R20Converter writes `data/actors.db`, `data/scenes.db`, and so on — one JSON
document per line. This is trivially inspectable, diffable, and requires nothing
but Python's standard library.

Two facts shape the decision:

1. **Foundry v13 still migrates NeDB to LevelDB automatically.** The storage
   format migration is triggered by the presence of `.db` files, and is
   independent of `coreVersion` and of the document schema migrations discussed
   in ADR-002. The Foundry CLI still ships `nedb-promises` as a runtime
   dependency for exactly this purpose. This migration is expected to be removed
   in v14, but it works today.
2. **There is no viable pure-Python LevelDB writer.** `plyvel` and `lvldb` both
   require the LevelDB C library. Bundling a C extension into the cx_Freeze
   Windows build would be a significant, platform-specific regression risk for a
   tool whose primary audience runs a downloaded `.exe`. No production-quality
   pure-Python LevelDB implementation exists.

## Decision

**Continue writing NeDB `.db` files, and rely on Foundry v13's storage-format
migration.** Do not add a native LevelDB dependency now.

Record the intended path for when v14 removes NeDB support: shell out to the
official [`@foundryvtt/foundryvtt-cli`][cli] (`fvtt package pack`, or its
`compilePack()` API) as an **optional post-processing step**. That means:

- The converter's own output stays pure Python and dependency-free.
- Users who have Node.js get native LevelDB output; users who do not still get a
  world that works on v13.
- We use Foundry's own packing implementation rather than reverse-engineering
  the on-disk format, so we inherit its correctness.

This is deliberately *not* implemented yet: it is dead weight until either v14
lands or a user needs it, and ADR-002's document schema port is the change that
actually determines whether the output works at all.

## Alternatives considered

- **Add `plyvel` as a dependency and write LevelDB directly.** Rejected for now.
  It requires a C toolchain or a prebuilt wheel on Windows, complicates the
  cx_Freeze build that ADR-001 just stabilised, and the exact key encoding
  Foundry's `classic-level` uses is not documented — we would be guessing
  against a closed-source consumer with no way to test.
- **Require Node.js and always invoke the Foundry CLI.** Rejected. It adds a
  hard runtime dependency on a toolchain that most of our users — who run a
  bundled Windows executable — do not have, in exchange for a format conversion
  Foundry currently performs for free.
- **Reverse-engineer and write LevelDB SST files from scratch.** Rejected. High
  effort, high risk, zero differentiating value, and a maintenance burden every
  time the format is revised.

## Consequences

- No new dependencies; the build described in ADR-001 is unaffected.
- Output remains human-inspectable, which materially helps debugging conversion
  problems and keeps the test suite simple.
- Users see Foundry's one-time "migrating world data" step on first launch. This
  should be mentioned in the README so it is not mistaken for an error.
- **This is a deadline, not a resolution.** When Foundry v14 removes the NeDB
  migration, R20Converter's output stops working until the CLI-based packing
  step is implemented. That work should begin as soon as a v14 prototype makes
  the removal concrete, and this ADR should then be superseded.

[cli]: https://github.com/foundryvtt/foundryvtt-cli
