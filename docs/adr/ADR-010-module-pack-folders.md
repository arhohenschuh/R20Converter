# ADR-010: Preserve the Roll20 folder hierarchy in module compendium packs

- **Status**: Accepted
- **Date**: 2026-08-12
- **Supersedes**: —
- **Superseded by**: —

## Context

`--export-as-module` throws the folder tree away on purpose. Four places clear
it, and one omission completes the picture:

| where | what it does |
| --- | --- |
| `Handout.__init__` | `if export_as_module: parent = None` |
| `Actor.__init__` | `if export_as_module: folder = None` |
| `Scene.__init__` | `if export_as_module: folder = None` |
| `Actor.exportItem` | `if export_as_module: folder_id = None` |
| `R20Converter.convert` | never constructs `Folders` on the module branch |

So a converted module imports as one flat list per pack. Worlds do not have this
problem: they build `folders.db` from the same Roll20 `journalfolder` tree that
the module branch discards.

**This is not a cosmetic loss.** Measured across the 18 adventure modules this
converter produced: **5,108 journal entries, every one of them in a single flat
Handouts folder**. Restoring the trees afterwards needed a separate tool chain,
a new offline gate, a live import gate and 18 re-releases, and recreated
**531 folders** that the converter had already computed and then dropped.
Document conservation is not navigation conservation.

Two things that could have blocked this are already settled:

1. **The storage format is known.** A pack keeps its folder tree under
   `!folders!<id>`, and `leveldb_pack.NON_DOCUMENT_COLLECTIONS` already names
   that prefix so the reader skips it. Writing it is the missing half of a
   round trip the code half-implements.
2. **The tree is already parsed.** `Folders.addJournalFolder` walks
   `journalfolder`, splits it per document type, and prunes a branch that would
   ship empty. None of that has to be invented.

One trap is worth recording. Foundry's `Folder#sorting` defaults to `"a"` —
alphabetical. A correct tree with the default sort still reorders the adventure:
*Part 3* lands before *Part 12*, and an "Introduction" folder sorts into the
middle. Preserving the tree without preserving the order finishes half the job.

## Decision

**Build the folder tree for module exports and write it into each pack.**

- `R20Converter.convert` constructs `Folders` on the module branch, before the
  journal, actors and items that reference it.
- The four `folder = None` overrides are removed.
- `DatabaseFile.save` writes `!folders!` entries alongside the documents,
  **filtered to the folder type that pack holds**, so each pack carries a
  self-contained, type-homogeneous tree.
- Every generated folder is emitted with `sorting: "m"` and an explicit `sort`.

World output is unchanged: it keeps writing `folders.db` exactly as before.

## Alternatives considered

- **Leave it to post-conversion tooling** (the status quo). Rejected. It is
  per-module work that must be repeated for every future conversion, it needs
  its own gate to prove it did not damage anything else, and it reconstructs
  information the converter held in memory and deliberately deleted.
- **Emit one shared `folders` pack.** Rejected: Foundry scopes compendium
  folders to the pack that contains them, so a shared pack would be ignored.
- **Keep Foundry's default alphabetical sorting.** Rejected. The Roll20 order is
  authored order; alphabetical is a different document, quietly.
- **Only fix the journal.** Rejected as arbitrary. The same override exists for
  actors, scenes and exported items, and the tree is already computed for all of
  them.

## Consequences

- A converted module imports with its Roll20 navigation intact, in source order.
- Folder ids derive from Roll20 ids through `Entity.normalizeID`, so repeat
  conversions stay byte-stable and a re-conversion does not orphan anything.
- Existing published modules are untouched until they are rebuilt. This ADR
  changes the converter, not the archives it produced.
- A pack is no longer a pure document store. The reader already skips
  `!folders!`, and `readPack` is what tests and debugging use, so the round trip
  stays honest.
- Empty folders are still not shipped: the existing prune in
  `addJournalFolder` decides, and it now decides for modules too.
- Filtering by type is load-bearing. A folder whose parent lives in another pack
  would be an orphan; keeping each tree type-homogeneous is what prevents it.
