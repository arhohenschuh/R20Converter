# B049: An asset missing from the export zip is abandoned instead of downloaded

- **Status**: **Fixed** — `Entity.copyZipFile` in `src/entities/base.py` now falls through to `downloadResource` when the asset is absent from the export zip. Tests: `tests/test_asset_and_compendium_fixes.py`.
- **Severity**: High (silent; cost 116 assets on a single campaign)
- **Found**: 2026-08-05, converting *Dragoncoast Danger*
- **Component**: `src/entities/base.py` (`copyZipFile`)
- **Related**: B048 (no CDN host fallback). Both must be fixed for either to help much.

## Symptom

```
Cannot find file 'journal\006 - Handouts\002 - Im Besitz der SCs\000 - … \avatar.webp' in Zip
```

116 such lines on one conversion. Each one is an asset the finished world simply does not
have — 110 of them handout avatars, so 110 handouts converted with no artwork at all.

The conversion exits **0**.

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

| | count |
|---|---:|
| matched to a URL in `campaign.json` | 111 |
| **recovered by fetching that URL** | **112** ¹ |
| genuinely dead after 32 variants on both hosts | 3 |
| degenerate (0 × 0 graphic, correctly skipped) | 1 |

¹ 111 by name plus one more found by a resolution-variant search.

So **97%** of what the converter discarded was still downloadable at conversion time. It
was not fetched because this code path does not fetch.

Note the interaction with B048: a fallback added today would still fail, because the fetch
would go to `s3.amazonaws.com` and 403. **B048 and B049 have to be fixed together** —
either alone recovers almost nothing.

## Suggested fix (not implemented)

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
