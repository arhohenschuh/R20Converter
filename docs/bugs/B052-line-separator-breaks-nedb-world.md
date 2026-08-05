# B052: a raw U+2028 in converted text makes a NeDB world unloadable

- **Status**: **Not a converter defect.** Traced to a post-conversion repair tool; the
  converter's own output is already safe. Repaired in the affected pack; a QA gate now blocks it.
- **Severity**: **Critical** where it occurs — the world cannot be opened at all, and the
  error names no file
- **Found**: 2026-08-05, first-ever launch of *Dragoncoast Danger* (pipeline item O10)
- **Component**: none in this repository — see *Who actually wrote it*

## Symptom

Foundry refuses to launch the world. The only diagnostic is:

```
Performing one-time migration of table "actors" from NEDB to LevelDB
The requested World "dragoncoast-danger" could not be auto-launched as it encountered an error.
2% of the data file is corrupt, more than given corruptAlertThreshold (0%).
Cautiously refusing to start NeDB to prevent dataloss.
    corruptItems: 2, dataLength: 89
```

No filename, no record id, and the world is left half-migrated: Foundry has already created
`data/actors/` and `data/effects/` as LevelDB directories before it fails.

## Why every offline check said the file was fine

`actors.db` holds **88** records. Validating it the obvious way reports a clean file:

| check | result |
|---|---|
| `split('\n')` + `JSON.parse` per line | 88 parsed, **0 unparseable** |
| records missing `_id` | 0 |
| NeDB's own `model.deserialize` per line | 88, **0 corrupt** |
| trailing newline / CRLF / BOM | LF only, no CR, no BOM |

Yet NeDB reports `dataLength: 89`. That mismatch is the whole finding: **NeDB is seeing one
more line than the file contains.**

## Cause

One document — the NPC *Marshy*, a satyr whose biography came across from Roll20 — contains a
raw **U+2028 LINE SEPARATOR** inside its HTML.

U+2028 is legal, unescaped, inside a JSON string, and `JSON.stringify` emits it raw. But NeDB
stores one record per line and reads through a line splitter that treats U+2028 (and U+2029
PARAGRAPH SEPARATOR) as line terminators. So the single record is split into two fragments,
neither of which parses:

```
88 records − 1 split record + 2 fragments = 89 lines, 2 corrupt   ->  2.25% > 0%
```

which is exactly what NeDB reported. The arithmetic is the proof.

## Scope, measured

| Pack | Store | Raw separators | Effect |
|---|---|---:|---|
| `dragoncoast-danger` | **NeDB** | **1** | **world will not load** |
| `dragons-of-icespire-peak` | LevelDB | 4 | none |
| `the-shattered-obelisk` | LevelDB | 2 | none |
| storm / wardens / out-of-the-abyss / lost-mine | — | 0 | none |

Only NeDB is line-based, so only a NeDB pack is affected. Dragoncoast is the last pack still
on NeDB, which is why this surfaced now and not months ago.

## Who actually wrote it

The first draft of this report blamed the converter and proposed escaping the separators in
`Entity.__str__`. That fix would have been **dead code**: `json.dumps` defaults to
`ensure_ascii=True`, which escapes *every* non-ASCII character, U+2028 included.

```
>>> json.dumps({'bio': 'a\u2028b'})
'{"bio": "a\\u2028b"}'          # already escaped
```

Comparing two copies of the same table settled it:

| copy | raw non-ASCII | umlauts | `\u00xx` escapes | raw U+2028 |
|---|---:|---:|---:|---:|
| converter output (`_pristine`) | **0** | 0 | 141 | **0** (1 escaped) |
| the file that would not load | 493 | 73 | 0 | **1** |

A file the converter wrote contains no raw non-ASCII at all. The failing file contains 493 —
so it had been **re-serialised by JavaScript**. `JSON.stringify` escapes neither non-ASCII nor
U+2028, so any pipeline tool that reads a NeDB table, edits it and writes the lines back turns
a safe file into an unloadable one. Roughly thirty `fix-*.mjs` / `o8-*.mjs` tools in
`Foundry_Pipeline_Build\_tools` do exactly that.

The lesson generalises past this bug: **a defect found in a converted pack is not
automatically a converter defect.** Check what the converter actually emitted before changing
it — the plausible fix here was to the wrong component and would have silently done nothing.

## Fix

Any tool that rewrites a NeDB table must escape both separators after `JSON.stringify`:

```js
const line = JSON.stringify(doc)
  .replace(/\u2028/g, '\\u2028')
  .replace(/\u2029/g, '\\u2029');
```

The parsed value is identical, so this is safe to apply unconditionally. Gate A **G19** is the
real protection, because it catches the condition no matter which tool introduced it.

## Repair for already-converted packs

`Foundry_Pipeline_Build\_tools\qa\fix-line-separators.mjs --pack <dir> [--apply]`

Escapes the raw separators in NeDB tables, reports LevelDB occurrences as harmless, and names
the records NeDB cannot read. Applied to Dragoncoast (1 occurrence); the world then launched
and completed its NeDB→LevelDB migration normally.

## Guard

Gate A **G19** fails a pack that carries a raw U+2028/U+2029 in a NeDB table, so this cannot
reach a release again. It is deliberately *not* a failure for LevelDB, which is not
line-based — flagging those would be noise.

## Diagnostic worth keeping

When a count from a tool disagrees with a count from the application, the difference is the
finding. Reproducing NeDB's own line splitter — including U+2028 — was what located the
record; `JSON.parse` over `split('\n')` never could, because it splits on the same characters
the file is valid under.
