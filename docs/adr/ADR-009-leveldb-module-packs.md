# ADR-009: Write LevelDB compendium packs for modules

- **Status**: Accepted
- **Date**: 2026-08-03
- **Supersedes**: ADR-003 (partially — worlds keep NeDB)
- **Superseded by**: —

## Context

ADR-003 decided to keep writing NeDB `.db` files and let Foundry migrate them,
and closed with an explicit expiry:

> **This is a deadline, not a resolution.** When Foundry v14 removes the NeDB
> migration, R20Converter's output stops working until the CLI-based packing
> step is implemented.

Foundry 14.365 is now the reporter's live version, so the deadline is due for
review. Two of ADR-003's three grounds for rejection have since become false:

1. *"It requires a C toolchain or a prebuilt wheel on Windows."* A prebuilt
   wheel now exists for the exact frozen interpreter:
   `plyvel_ci-1.5.1-cp38-cp38-win_amd64.whl`. Installed into the build
   environment it imports and round-trips a database with no compiler present.
2. *"The exact key encoding Foundry's `classic-level` uses is not documented —
   we would be guessing against a closed-source consumer with no way to test."*
   The encoding has now been **read directly** out of a published module that
   runs on 14.365 (`lost-mine-of-phandelver-1.2.0`), and that module is a
   reference to test against.

The third ground — that the output should stay inspectable and dependency-free —
still holds, and is what limits the scope below.

### The measured format

| aspect | finding |
| --- | --- |
| primary key | `!<collection>!<docId>` |
| embedded key | `!<collection>.<embedded>!<parentId>.<childId>` |
| value | plain UTF-8 JSON, uncompressed |
| parent document | embedded collections are replaced by **arrays of child ids** |
| collections split | `actors.items`, `journal.pages`, `tables.results`, `scenes.{walls,tokens,tiles,lights,drawings}` |

This is a restructuring, not a file-format swap: one scene in the reference
holds 1,382 wall *ids* while 1,382 separate `!scenes.walls!…` entries hold the
wall documents.

### What the user actually needs

The reporter's publishing pipeline was: convert → fix offline → import into
Foundry so the packs get converted → fix again → re-export → package. Only the
third step is addressed here. Worlds do not need it: Foundry's NeDB→LevelDB
world migration was measured lossless on 14.365, is automatic, and costs the
user nothing.

## Decision

**Write LevelDB directly for module compendium packs. Keep NeDB for worlds.
Keep `coreVersion: 13`.**

- `--export-as-module` writes `packs/<name>/` LevelDB directories.
- World conversion is untouched and keeps writing `data/*.db`.
- The document schema is unchanged. This ADR is about *storage*, not schema;
  ADR-002's v13 target and `DOCUMENT_SCHEMA_CORE_VERSION = "13"` stand, and
  Foundry's v13→v14 document migration remains the accepted path (B043).
- `plyvel` is an **optional** dependency. It is bundled in the frozen build, so
  every `.exe` user gets LevelDB. A source install without it falls back to
  NeDB and says so.

## Alternatives considered

- **Shell out to `foundryvtt-cli`** (ADR-003's recorded plan). Rejected: it adds
  a Node.js runtime dependency for the majority of users who run a bundled
  `.exe`, to do work a 470 KB wheel already does in-process.
- **LevelDB for worlds as well.** Rejected as scope. The world migration is
  automatic and measured lossless, so this would add risk and a native
  dependency to the world path in exchange for nothing the user can perceive.
- **Hand-rolled SSTable writer.** Rejected, unchanged from ADR-003: high effort,
  high risk, zero differentiating value.
- **Make LevelDB mandatory.** Rejected. A hard native dependency would mean a
  failed import produces no output at all; degrading to the format that has
  worked all along is strictly better.

## Consequences

- Published modules install without the import-and-re-export round trip.
- The frozen build gains a native `.pyd`. This is the risk ADR-001 warned about
  and is why the build is verified by loading the module in the frozen
  interpreter, not merely by the build exiting zero.
- Module packs stop being greppable newline JSON. Mitigated by keeping the NeDB
  writer in place for worlds and by a reader used in tests, so a pack can still
  be dumped when a conversion needs debugging.
- The embedded-document split is the correctness risk, not the encoding: an
  orphaned child or an id present in a parent array with no matching entry is
  silently missing content. Tests assert both directions of that relationship.
- If a future Foundry changes the layout, this ADR is the place to revisit; the
  reference module makes the change detectable.
