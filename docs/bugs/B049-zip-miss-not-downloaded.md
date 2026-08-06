# B049: An asset missing from the export zip is abandoned instead of downloaded

- **Status**: **Fixed — and keep the fix.** `Entity.copyZipFile` in `src/entities/base.py` falls through to `downloadResource` when the asset is absent from the export zip. Tests: `tests/test_asset_and_compendium_fixes.py`.
  ⚠ **Re-diagnosed 2026-08-06: this was not the root cause.** 111 of the 116 assets were in the zip all along, under a path the converter derived one digit wrong (**B053**). This fallback masked that defect for a day by quietly downloading what was already on disk. It is still worth having — see the addendum below — but it is a safety net, not the cure.
- **Severity**: High (silent; cost 116 assets on a single campaign)
- **Found**: 2026-08-05, converting *Dragoncoast Danger*
- **Component**: `src/entities/base.py` (`copyZipFile`)
- **Related**: **B053 (the actual root cause)**; B048 (no CDN host fallback). Both must be fixed for either to help much.

## Symptom

```
Cannot find file 'journal\006 - Handouts\002 - Im Besitz der SCs\000 - … \avatar.webp' in Zip
```

116 such lines on one conversion. Each one is an asset the finished world simply does not
have — 110 of them handout avatars, so 110 handouts converted with no artwork at all.

The conversion exits **0**.

> **Superseded — see Addendum 2.** The reading above is what the log appeared to say. In
> fact 111 of the 116 were in the zip under `journal/007 - Handouts/`; the converter looked
> in `006`. The warning text is accurate about the path it tried and misleading about what
> that implies.

## Cause

`copyZipFile` receives the asset's **URL** and the zip path. When the zip does not hold the
file it logs and gives up, without ever trying the URL it was handed:

```python
if zipfile is None:
    self.logWarning("Cannot find file '%s' in Zip" % filename)
    return (None, "")
```

`downloadResource` — the sibling method that would fetch exactly this — is never reached.
The export zip is treated as the only possible source, even though R20Exporter routinely
fails to bundle assets it references. On *Dragoncoast Danger* it omitted **116 of them**,
while `campaign.json` still carried a working URL for **111**.

## Evidence

Of the 116 zip-misses on *Dragoncoast Danger*:

| outcome | count |
|---|---:|
| recovered by fetching the URL | **112** ¹ |
| genuinely dead after 32 variants on both hosts | 3 |
| degenerate (0 × 0 graphic, correctly skipped) | 1 |
| **total** | **116** |

¹ 111 matched to a URL in `campaign.json` by name, plus one more found by a
resolution-variant search.

So **112 of the 115 real misses (97%)** were still downloadable at conversion time. It
was not fetched because this code path does not fetch.

Note the interaction with B048: a fallback added today would still fail, because the fetch
would go to `s3.amazonaws.com` and 403. **B048 and B049 have to be fixed together** —
either alone recovers almost nothing.

## Addendum (6 Aug 2026) — the tally is correct; the table was not

Raised during the R20Exporter roadmap review as a suspected off-by-one. **It is not one.**
The original figures are right and the partition closes exactly:

```
112 recovered + 3 dead + 1 degenerate = 116
```

Two things caused the false alarm, and both are worth keeping:

**1. The table mixed a subset into a partition.** The original first row was
*"matched to a URL in `campaign.json` — 111"*, sitting above *"recovered — 112"* as though
the two were sibling categories. They are not: the 111 are a **subset** of the 112 (the
112th was found by variant search, as the footnote said). A reader summing the column got
`111 + 112 + 3 + 1 = 227`, and a reader checking the partition got `112 + 3 = 115 ≠ 116`.
Either way the table appeared broken while every number in it was correct. It has been
restructured above so the rows are disjoint and the total is stated explicitly; the 111
lives in the footnote where it belongs, as provenance for how the 112 were found.

**2. The reviewer's own measurement was at fault.** The suspicion came from a grep matching
`\b\d{2,4}\b`, which silently skipped the `degenerate … | 1` row because its count is a
single digit. The check was vacuous for exactly one row, and that row was the missing one.
This is the pipeline's own rule turned on itself: *a count that disagrees with another count
is a finding — but confirm which of the two is wrong before believing either.*

**Denominator note.** 112/116 = 96.6% and 112/115 = 97.4%; both round to the 97% originally
quoted, so no downstream statement changes. The sharper form is **112 of 115 real misses**,
since the degenerate 0 × 0 graphic was never a recoverable asset.

## Addendum 2 (6 Aug 2026) — the assets were never missing

Prompted by a re-export of *Dragoncoast Danger*, on the theory that the CDN had rotted and
a fresh pull would recover the 3 dead assets. Comparing the two zips instead overturned the
whole diagnosis.

**The new export contains no more artwork than the old one.** Both hold every asset the
campaign references; the set of files present only in the older zip is **empty**. Nothing
had been lost to CDN rot, so there was nothing for a re-export to recover — and by
implication, nothing had been missing from the *original* zip either.

That forced the question the original investigation never asked: *if the file was in the
zip, why did the converter not find it?* Splitting the 116 warnings by folder answers it
immediately:

| miss location | lines | distinct assets | verdict |
|---|---:|---:|---|
| `journal\006 - Handouts\…` | 111 | 111 | **present in the zip, under `journal/007 - Handouts/`** |
| `pages\…\graphics\…` | 5 | 4 | genuinely absent — the exporter itself reports these as `failed` |
| **total** | **116** | **115** | |

The exporter's own `export_report.json` lists exactly `failed: 4`, and those four URLs are
precisely the four distinct assets in the second row. The two independent counts agree.

**Root cause.** `campaign.json`'s `journalfolder` tree holds one entry at index 5 that the
converter did not recognise — `-NULVBUBpNdmYpeOc2nH`, a PDF ("City Encounters Master
Table"), one of **8** PDFs in this campaign. The exporter numbers every sibling it writes;
`Journal.addToFolder` advanced its index only for handouts and characters. One unrecognised
sibling put Handouts at 6 where the zip had 7, and every asset below it followed the wrong
path. Filed as **B053**.

**Verification.** Re-converting with B053 fixed:

| export | manifest? | `Cannot find file` lines before | after |
|---|---|---:|---:|
| 6 Aug (`R20Export-1.0.0`) | yes — 488 URLs resolved | 116 | **5** |
| 4 Aug (`R20_Export_V1.1`) | no | 116 | **5** |

The residual 5 lines are the 4 exporter-reported failures (one asset referenced twice). The
legacy column matters: it is the same 116 → 5 with no manifest at all, which proves the
path-derivation fix carries the repair on its own and the manifest is belt-and-braces.

**Keep the fallback anyway.** It did not cure this defect, but the four genuine failures
above are real, and an export that omits an asset it still has a live URL for remains a
case worth handling. What changes is its *status*: a download fallback firing in bulk is now
understood as a **symptom of path drift**, not as normal wear. `copyZipFile` therefore counts
misses and warns once past 25 (`noteZipMiss`) when no manifest is present — so the next time
a whole folder goes missing, it announces itself instead of being silently papered over.

**Lesson.** *A workaround that succeeds hides the defect it worked around.* The fallback
worked: it fetched 112 of the assets and the world looked correct, which is exactly why
nobody asked why 111 of them had been "missing" from a zip that contained them. A repair
that quietly restores the expected output removes the pressure to explain the anomaly.
Prefer a fix that is loud about how often it is needed.

## Fix (implemented)

Fall back to the network before giving up:

```python
if zipfile is None:
    self.logWarning("Cannot find file '%s' in Zip" % filename)
    if url:
        # R20Exporter regularly omits assets it references; the URL usually still works.
        return self.downloadResource(url, destination, type=type, dedup=dedup)
    return (None, "")
```

`downloadResource` already handles dedup naming, the resource cache and destination paths,
so the fallback is one call rather than a second implementation.

Worth adding alongside: distinguish the two outcomes in the log. *"Not in zip, recovered by
download"* and *"not in zip, download failed"* are very different states, and today both
read as `Cannot find file … in Zip`.

## Why it matters beyond the missing pixels

A missing avatar is not just cosmetic here. The handout art *is* the handout — several of
the 110 are letters, maps, ledgers and notes that the players are meant to read. A handout
with its image dropped is an empty document.
