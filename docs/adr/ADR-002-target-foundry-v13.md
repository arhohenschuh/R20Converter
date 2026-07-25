# ADR-002: Target Foundry VTT v13+

- **Status**: Accepted
- **Date**: 2026-07-25
- **Supersedes**: —
- **Superseded by**: —

## Context

R20Converter emits a world whose `world.json` declares `"coreVersion": "9.245"`,
`"minimumCoreVersion": "0.0.0"` and `"compatibleCoreVersion": "1.0.0"`, and whose
`module.json` declares `"minimumCoreVersion": "0.7.5"` with the long-removed
`entity` key on each compendium pack. Every document it writes uses the Foundry
v9 schema: `permission` rather than `ownership`, `data` rather than `system`,
`Actor#token` rather than `Actor#prototypeToken`, `JournalEntry#content` rather
than `pages[]`, flat `Scene#img`/`gridType`/`shiftX` rather than the `background`
and `grid` inner objects, and so on.

Foundry has moved on considerably. The current generation is **v13**.

The tempting assumption is that this does not matter, because Foundry migrates
old worlds on launch. **That assumption is false**, and verifying it is the
central finding behind this ADR.

Foundry issue [#10164][10164], *"Finalize breaking changes and deprecations from
V10 and earlier which have reached the end of their compatibility period"*
(closed 2023-11-06, milestone **V12 Prototype 1 — 12.316**), removed the
automatic v9 → v10 data migrations wholesale. Directly quoted from that issue:

- "Remove automatic migration of the v9 `Document#data` field"
- "Removed automatic migration of the `Document#permission` field"
- "Removed automatic migration of v9 `Actor#token` field"
- "Remove automatic migration of v9 JournalEntry content to V10 journal entry pages"
- "Removed migration of certain v9 `Scene` fields related to the grid / background texture"
- "Removed support for the following v9 `Token` fields in favor of the `Token#texture` / `Token#sight` inner objects"
- "Removed automatic migration of v9 `ChatMessage#roll`", "`Folder#parent`",
  "`RollTableResult#resultCollection`", "`TileDocument#img`",
  "`NoteDocument#icon`", "`DrawingDocument#type/width/height/points`",
  "`Wall#sense`"

Those shims lived only in v10 and v11. A world that has never been opened in
v10 or v11 therefore has no path forward: **v12 and v13 will load our documents
verbatim, with fields they no longer understand.** No value of `coreVersion`
changes this — claiming `13.x` skips migration, and claiming `9.245` runs a
migration chain whose v9 steps no longer exist. Both produce a world with
actors that have no system data, journals with no pages, and scenes with no
background.

The one thing that *does* still work is the storage-format migration: v13 still
converts NeDB `.db` files to LevelDB (see ADR-003). That is independent of
`coreVersion` — and it is a hollow victory, because it yields a LevelDB database
full of documents Foundry cannot read.

## Decision

**Foundry VTT v13 is the target platform.** Concretely:

1. Every Foundry version number, compatibility range and schema constant lives
   in a single module, `src/foundry.py`. Version numbers were previously
   scattered as string literals across `world.py`, `module.py` and
   `R20Converter.py`, which is precisely why they drifted apart and why three
   different, mutually inconsistent compatibility declarations existed.
2. `world.json` and `module.json` are emitted in the v13 manifest schema: `id`
   instead of `name`, a required `type`, a `compatibility` object instead of
   `minimumCoreVersion`/`compatibleCoreVersion`, `relationships` instead of
   `dependencies`, `authors` instead of `author`, and compendium packs keyed by
   `type` (not `entity`) with `ownership` and an extension-less `path`.
3. `coreVersion` in `world.json` is written from the same constant that
   describes the document schema we emit — never hardcoded independently. It is
   the field Foundry uses to decide which migrations to run, so it must always
   tell the truth about our output.
4. Porting the document writers to the v13 schema is tracked as an explicit,
   per-document-type milestone (below). Until a document type is ported, it is
   emitted in its current form; the manifest work does not pretend the documents
   are ready.

### Document schema port — remaining work

| Document | Change required | File |
| --- | --- | --- |
| all | `permission` → `ownership` | `journal.py`, `tables.py`, `playlists.py`, `macros.py`, `actors.py`, `items.py`, `scenes.py` |
| Actor, Item | `data` → `system` | `actors.py`, `items.py`, `base.py` |
| Actor | `token` → `prototypeToken` | `actors.py` |
| JournalEntry | `content`/`img` → `pages[]` | `journal.py` |
| Scene | `img`/`shiftX`/`shiftY` → `background.{src,offsetX,offsetY}` | `scenes.py` |
| Scene | `gridType`/`gridColor`/`gridAlpha`/`gridDistance`/`gridUnits` → `grid.*` | `scenes.py` |
| Token | `img`/`tint` → `texture.{src,tint}`; `scale`/`mirrorX`/`mirrorY` → `texture.scaleX/scaleY` | `scenes.py` |
| Token | `vision`/`dimSight`/`brightSight`/`sightAngle` → `sight.*` | `scenes.py` |
| Token | `dimLight`/`brightLight`/`lightAngle`/`lightColor`/`lightAlpha`/`lightAnimation` → `light.*` | `scenes.py` |
| Tile | `img`/`tint` → `texture.*` | `scenes.py` |
| Note | `icon`/`tint` → `texture.*` | `scenes.py` |
| Drawing | `type`/`width`/`height`/`points` → `shape.*` | `scenes.py` |
| AmbientLight | `dim`/`bright`/`angle`/`tintColor`/`tintAlpha`/`lightAnimation`/`darkness` → `config.*` | `scenes.py` |
| Wall | `sense` → `sight` + `light` | `scenes.py` |
| RollTableResult | `resultCollection`/`resultId` → `documentCollection`/`documentId` | `tables.py` |
| Folder | `parent` → `folder` | `folders.py` |
| ChatMessage | `roll` → `rolls` | `chat.py` |

## Alternatives considered

- **Keep emitting v9 documents and let Foundry migrate.** Rejected: verified
  impossible. The migration code was deleted in 12.316.
- **Emit v9 documents and tell users to open the world once in Foundry v11
  first.** Rejected. It requires users to install an obsolete Foundry version
  purely to launder our output, it will stop working entirely when v11 is no
  longer downloadable, and it makes a two-step manual process out of a tool
  whose entire value proposition is automation.
- **Target v12 and rely on the v12 → v13 migration.** Rejected. That migration
  chain does exist, so it would work, but it buys nothing: we would be
  deliberately writing a schema that is already one generation stale on the day
  we ship it, and would have to do this work again for v14.
- **Support both v9 and v13 output behind a flag.** Rejected for now. It doubles
  the surface area of the least-tested part of the codebase to serve users on a
  Foundry generation that is several years old. It can be revisited if demand
  appears; the constants module makes it a smaller change than it would have
  been.

## Consequences

- Worlds produced by R20Converter will load in Foundry v13 without a migration
  step, once the document port is complete.
- Output is **no longer usable on Foundry v9–v11**. This is a breaking change
  and must be called out in the README and the changelog.
- The per-document-type port is substantial and touches the largest, least
  tested files in the project (`actors.py`, `scenes.py`, `items.py`). ADR-004's
  test suite exists specifically to make that work safe.
- A single constants module means the next generation bump (v14) is a small,
  reviewable change rather than an archaeology exercise.

[10164]: https://github.com/foundryvtt/foundryvtt/issues/10164
