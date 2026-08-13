# ADR-011: Scene folders come from an explicit manifest, never inference

- **Status**: Accepted
- **Date**: 2026-08-12
- **Supersedes**: —
- **Superseded by**: —

## Context

ADR-010 restores the folder tree that Roll20 actually exports. Scenes have no
such tree to restore: **Roll20 has no folder concept for pages.** The journal
has `journalfolder`; pages are a flat, ordered list. Whatever chapter structure
an adventure has lives in its prose and, sometimes, in page names.

The demand is real even though the source data is not. *Against the Giants*
ships 8 pages that belong to 3 chapters — *Steading of the Hill Giant Chief*,
*Glacial Rift of the Frost Giant Jarl*, *Hall of the Fire Giant King* — plus a
`Start` page that belongs to none of them. Nothing in the export says so.

The tempting shortcut is to infer chapters from page names. It does not survive
contact with the exports this converter is fed: names are inconsistent between
adventures, sometimes numbered and sometimes not, sometimes prefixed with the
chapter and sometimes with the level, and occasionally duplicated between
chapters. An inference that is right for one adventure and wrong for the next is
worse than no inference, because it is wrong *silently* — the scenes are all
present, in plausible folders, and nobody re-reads a folder tree that looks
fine.

## Decision

**Take the chapter structure as declared input, and fail closed on anything
ambiguous.**

- `--scene-folders <manifest.json>`, schema `r20converter-scene-folders/v1`.
- The manifest declares an optional root folder, an ordered list of chapter
  folders, the ordered scenes inside each, and the scenes that sit at the root
  next to those folders.
- A scene is referenced by its Roll20 page **name**, which is what an author can
  read off the Roll20 UI, or by `{"id": "-Abc…"}` when names collide.
- A reference that matches **no** page, or **more than one**, aborts the
  conversion. So does declaring the same page twice.
- Pages the manifest does not mention stay at the root and are logged.
- Without the option nothing changes: no scene folders are generated.

Folders are emitted with `sorting: "m"` and explicit `sort` values, per ADR-010,
so the declared order is the order the GM sees.

## Alternatives considered

- **Infer chapters from page-name prefixes.** Rejected, as above: unreliable
  across adventures and silent when wrong.
- **Infer from page order alone** (fixed-size groups). Rejected: chapters are
  not equal-length, and a page inserted upstream shifts every later group.
- **Reuse the Automation pipeline's `r20-scene-folders/v1` manifest.** Rejected
  as an input format, deliberately. That schema addresses *Foundry* document
  ids, which exist only after conversion; the converter needs to resolve Roll20
  pages before those ids are minted. Two schemas with different key spaces is
  clearer than one schema that means different things at different times.
- **Leave it to post-conversion tooling.** Rejected for the same reason as
  ADR-010, with one addition: the converter is the only place that still knows
  the Roll20 page order the manifest is expressed against.
- **Accept unknown references and drop them with a warning.** Rejected. A
  mis-typed chapter name would produce a module that looks organized and
  quietly leaves scenes elsewhere; a warning in a long conversion log is not a
  control.

## Consequences

- Chapter structure becomes a small, reviewable, diffable artifact that lives
  next to the adventure and can be corrected without reconverting.
- Someone has to author it once per adventure. That is the honest cost of
  information the source does not contain.
- A rename upstream in Roll20 breaks the manifest loudly, at conversion time,
  which is where it can still be fixed cheaply.
- Undeclared pages remaining at the root keeps the option additive: a partial
  manifest organizes what it names and cannot lose a scene.
- The converter gains a second input file. It stays optional, and the schema
  string is checked, so an unrelated JSON handed to the flag is rejected rather
  than half-read.
