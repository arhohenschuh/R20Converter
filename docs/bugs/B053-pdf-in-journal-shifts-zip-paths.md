# B053: a PDF in the journal tree shifts every later zip path by one

- **Status**: **Fixed** — `Journal.addToFolder` now counts every sibling the exporter numbers, `findID` resolves PDFs, and `copyZipFile` prefers the path recorded in `export_report.json` when the export ships one. Verified 116 → 5 misses on both a manifest-bearing and a legacy export. The B049 download fallback stays as a safety net.
- **Severity**: High (silent; cost 116 assets on *Dragoncoast Danger*, and was misattributed to the exporter for two days)
- **Found**: 2026-08-06, comparing a fresh R20Exporter 1.0.0 export against the 4 Aug export
- **Component**: `src/entities/journal.py` (`Journal.addToFolder`)
- **Related**: **B049** — the 116 "assets missing from the zip" are this bug. See the B049 addendum.

## Symptom

116 lines of:

```
Cannot find file 'journal\006 - Handouts\002 - Im Besitz der SCs\… \avatar.webp' in Zip
```

**111 of the 116 are under `journal\006 - Handouts\`.** The export zip contains
`journal/007 - Handouts/…`, with all 295 avatars present. Nothing was ever missing from the
export — the converter looked one folder-index too low.

## Cause

`journalfolder` is a single ordered array mixing **folders** (objects) with **loose entity
ids** (strings). The exporter numbers *every* sibling sequentially. `addToFolder` increments
its index only for a folder, a handout, or a character:

```python
handout = self.findID(item, "handout")
if handout != None:
    handouts.append(Handout(self, handout, index, folder_id, folder_path))
    index += 1
elif self.findID(item, "character") != None:
    index += 1
# any other entity type: index is NOT incremented
```

Roll20 also allows **PDFs** in the journal tree, and `findID` has no `"pdf"` case, so a PDF
entry is skipped without incrementing. Every sibling after it — including whole folders and
their entire subtrees — is then numbered one lower than the zip.

Reproduced exactly on *Dragoncoast Danger*:

| `journalfolder[i]` | resolves to | converter index | zip |
|---|---|---|---|
| [2] `-NsSA8jwAnc618rkJgRz` | character | 2 | `002 - Sheela Peryroyl` |
| [3] `-NsS9dUX13zZvr7QOvn5` | character | 3 | `003 - Zybilna` |
| [4] `-NqiDCYln4CSAoo8lAN_` | character | 4 | `004 - Marshy` |
| **[5]** `-NULVBUBpNdmYpeOc2nH` | **`campaign["pdfs"]`** — *City Encounters Master Table* | **skipped** | `005 - City Encounters Master Table` |
| [6] `-NULScLTFyA-_82jnMBL` | handout | 5 | `006 - City Encounters` |
| **[7]** folder *Handouts* | — | **6** | **`007 - Handouts`** ← the 111 misses |

That campaign carries **8** PDFs (`pdfs: 8/8` in the exporter's own report), so the drift is
not exotic. Any campaign with a PDF above other journal entries hits it.

## Scope

The same index-derivation pattern appears in `items.py`, `playlists.py`, `scenes.py` and
`tables.py`. Only the journal path is confirmed defective; the others should be audited for
the same assumption — *"every sibling I care about is a sibling the exporter numbered"*.

## Why it went unnoticed for so long

The B049 fallback **works**: when the zip lookup misses, the converter downloads the asset
from the URL in `campaign.json`, and 112 of 116 came back. A systematic path bug therefore
presented as an intermittent network annoyance. It cost 112 unnecessary fetches per
conversion and made the result depend on a live CDN that is measurably rotting — between
4 and 6 Aug, three Dragoncoast assets could no longer be fetched at original resolution
(16.4 MB → 4.8 MB on one avatar).

## Fix (implemented)

Two changes, smallest first.

**1. Count the siblings we skip** — `entities/journal.py`, plus a `"pdf"` case in
`Entity.findID` (`entities/base.py`) so PDFs are resolvable at all. The `pdf` lookup is
placed **last** in `findID`, so no id that already resolved changes meaning; only ids that
previously resolved to nothing can now resolve to a PDF.

```python
elif self.findID(item, "character") != None or self.findID(item, "pdf") != None:
    index += 1
```

This alone repairs legacy exports, which is most of the archive — it is the only fix that
can, since they carry no manifest.

**2. Prefer the exporter's recorded path when there is one.** R20Exporter 0.14.0+ ships
`export_report.json`, in which every asset carries the `path` it was actually written to.
`R20Converter.loadExportReport` builds a URL → path map at startup and `copyZipFile` consults
it before falling back to the derived name. Derivation cannot know about entity types the
converter does not consume; the manifest does not have to guess.

This is a second line of defence rather than the repair. Only **5 of the 23 exports** in the
local archive carry a manifest (Sunless Citadel 0.14.0, Curse of Strahd 0.15.0, Dragoncoast
1.0.0, Wardens 1.0.1, Storm 1.0.1); the other 18 predate it, and those are exactly the
exports behind every shipped pack.

Both paths remain in place: manifest first, derivation second, download third (B049).

**3. Make bulk drift audible.** `noteZipMiss` counts zip misses and warns once past 25 when
no manifest is present. The whole reason this survived two days is that the B049 fallback
repaired the damage silently.

## Verification

| export | manifest? | misses before | after |
|---|---|---:|---:|
| `Dragoncoast Danger_R20Export-1.0.0.zip` (6 Aug) | yes — 488 URLs | 116 | **5** |
| `Dragoncoast Danger_R20_Export_V1.1.zip` (4 Aug) | no | 116 | **5** |

The residual 5 lines are 4 distinct assets, and `export_report.json` independently reports
`failed: 4` for exactly those URLs. Output now writes `journal/007 - Handouts/` with 113
files, matching the zip.

Tests: `tests/test_asset_and_compendium_fixes.py` — `TestJournalFolderNumbering` (a PDF
sibling consumes an index; it shifts later subfolder names; an *unknown* id still does not
count, so the drift is not re-introduced in the other direction) and
`TestExportManifestPathWins` (manifest beats a wrong derivation; derivation still used with
no manifest; misses are counted). Each was confirmed to fail against the unfixed source
before being kept.

## Blast radius

Swept every export in the local archive (30 zips) by replaying `addToFolder`'s numbering both
ways and scoring the result against the directory names actually present in the zip — no
conversion required:

| campaign | PDFs | folders pre-1.7.4 | **handout dirs pre-1.7.4** | 1.7.4 |
|---|---:|---|---|---|
| **Dragoncoast Danger** | 8 | **2 / 29** | **5 / 130** | all correct |
| **Storm over Savage Frontier** | 7 | 68 / 68 | **397 / 448** | all correct |
| Wardens of the North | 3 | 59 / 59 | 353 / 353 | all correct |
| the other 27 | 0 | all correct | all correct | all correct |

**Two campaigns are affected, not one.** Holding PDFs is not sufficient — a skipped entity
shifts paths only when it sits **above** a folder or handout in sibling order — but the
condition has to be evaluated separately for each numbered sequence.

> ⚠ **The first version of this table was wrong, and the error is instructive.**
> `b053-drift-check.py` originally compared only journal **folder** names, and on that
> evidence this document stated "Dragoncoast is the only campaign affected". Storm scores a
> clean 68 / 68 on folders — and **51 of its 448 handout directories are still misnumbered**.
> Wardens' 3 PDFs really are harmless in both sequences; Storm's 7 are not. The tool was
> extended to score handout directories as well before any of these numbers were trusted.
>
> The measurable cost of believing the first table: Storm shipped 1.0.9 with **45 handout
> images missing** and Dragoncoast shipped 1.2.0 with **85 downgraded to CDN thumbnails**,
> 125.7 MB short. Both were repaired in Storm 1.0.10 / Dragoncoast 1.2.1 by rewriting the
> asset files from the export — the dedup filename derives from the source URL, so no
> document changes and no re-conversion was needed.

The check remains self-validating: it reproduces the known defect on Dragoncoast without
running the converter, so a clean result elsewhere means something — **as long as it is
pointed at every numbered sequence the exporter emits.**

## Follow-up

The `Scope` note above stands: `items.py`, `playlists.py`, `scenes.py` and `tables.py` share
the derivation pattern and have not been audited. They are lower risk now that the manifest
path exists for current exports, but legacy exports still depend entirely on derivation.


```python
# 1. count every entry the exporter numbers, not only the two types we consume
elif self.findID(item, "character") is not None or self.findID(item, "pdf") is not None:
    index += 1
```

`findID` needs a `"pdf"` case over `campaign["pdfs"]`; it currently knows only
handout/page/character/player/track.

**2. Fail loudly on systematic drift.** A single zip miss is plausible; a hundred is a
derivation bug. `copyZipFile` should count misses and, above a small threshold or when a
whole subtree misses, warn that the zip path derivation is suspect — the fallback then
remains a safety net instead of a disguise.

**Keep the B049 fallback either way.** It is correct behaviour for a genuinely absent asset,
and it is what kept Dragoncoast shippable.

## Verification

The new R20Exporter reports per-collection `exported` vs **live** counts and bundles
`index.json` (Roll20 id → type/name). Either would have identified `-NULVBUBpNdmYpeOc2nH`
as a PDF immediately. Once fixed, re-converting *Dragoncoast Danger* from the 6 Aug export
must produce **0** `Cannot find file … in Zip` warnings, against 116 today.
