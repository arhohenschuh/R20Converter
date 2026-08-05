# B048: Asset downloads never try Roll20's current CDN host, so every `s3.amazonaws.com` image is lost

- **Status**: **Fixed** — `Entity.hostCandidates` in `src/entities/base.py`; each resolution is tried on the current CDN host before the old one. Tests: `tests/test_asset_and_compendium_fixes.py`.
- **Severity**: High (silent, total for affected assets, and affects every conversion to date)
- **Found**: 2026-08-05, while converting *Dragoncoast Danger* and re-probing six shipped conversions
- **Introduced**: pre-dates 1.0 — the resolution walk was always host-blind
- **Component**: `src/entities/base.py` (`fixImageUrl`, `_fetchResource`)
- **Related**: B049 (no download fallback when an asset is missing from the export zip)

## Symptom

Art hosted on `s3.amazonaws.com` is never downloaded. The conversion completes, exits **0**,
and logs a warning per asset:

```
Error downloading 'https://s3.amazonaws.com/files.d20.io/images/…/original.png': HTTP 403
Error downloading 'https://s3.amazonaws.com/files.d20.io/images/…/max.png': HTTP 403
Error downloading 'https://s3.amazonaws.com/files.d20.io/images/…/med.png': HTTP 403
Error downloading 'https://s3.amazonaws.com/files.d20.io/images/…/thumb.png': HTTP 403
Failed to download URL : https://s3.amazonaws.com/files.d20.io/images/…/med.png
```

Four attempts, four 403s, asset abandoned. Downstream this looks like the art is *dead*,
and repair tooling has stripped `<img>` tags on that basis — see *Impact*.

## Cause

Roll20 renamed the host. `s3.amazonaws.com/files.d20.io/images/…` now answers **403** for
every object; the **same object** is served by `files.d20.io/images/…`.

`_fetchResource` degrades through Roll20's resolution variants but only ever varies the
*filename*:

```python
for pattern, replacement in ((r"/original\.([^/]*)$", r"/max.\1"),
                             (r"/max\.([^/]*)$",      r"/med.\1"),
                             (r"/med\.([^/]*)$",      r"/thumb.\1")):
```

`fixImageUrl` likewise only rewrites the resolution segment. **Neither touches the host.**
So all four candidates carry the dead host and all four 403.

The failure is loud per-line but invisible in aggregate: nothing counts the losses, and the
exit code is 0.

## Evidence

Sampled 14 asset URLs from each of six shipped campaign exports and probed both hosts:

| Export | urls in export | sampled | 200 on `files.d20.io` | 200 on `s3.amazonaws.com` | dead |
|---|---:|---:|---:|---:|---:|
| Wardens of the North S3 | 2,681 | 14 | 13 | 0 | 1 |
| Out of the Abyss | 1,115 | 14 | 14 | 0 | 0 |
| Dragons of Icespire Peak | 1,928 | 14 | 13 | 0 | 1 |
| The Shattered Obelisk | 1,266 | 14 | 14 | 0 | 0 |
| Lost Mine of Phandelver | 316 | 14 | 14 | 0 | 0 |
| Storm over Savage Frontier | 1,713 | 14 | 14 | 0 | 0 |
| **total** | **9,019** | **84** | **82** | **0** | **2** |

**82 of 84 alive on the renamed host. 0 of 84 on the host the converter uses.**

On *Dragoncoast Danger*, 116 assets were absent from the finished world; **112 were
recovered** by host substitution alone (plus one variant retry). All 112 answered 403 on
the original host and 200 on the renamed one.

## Impact

Every conversion produced so far is missing recoverable artwork. Worse, the 403s were
interpreted as "this art no longer exists", and Phase A tooling **deleted** `<img>` tags on
that basis — on *Wardens of the North* 197 tags were stripped and 110 rewritten against a
"69 alive / 139 dead" verdict that was measured on the dead host. The URLs survive only
because the source exports are immutable.

## Suggested fix (not implemented)

Make the host a candidate axis rather than a constant: try one host, fall back to the
other, then walk the resolutions as today.

```python
# Roll20 renamed its CDN. s3.amazonaws.com/files[.staging].d20.io/… now 403s for
# every object; the bare host serves the same bytes. Try the working host first
# and keep the old one as a fallback, so nothing breaks if Roll20 reverts.
_S3 = re.compile(r"^https?://s3\.amazonaws\.com/(files(?:\.staging)?\.d20\.io)(/.*)$")

def _hostCandidates(self, url):
    m = _S3.match(url)
    if m:
        return ["https://%s%s" % (m.group(1), m.group(2)), url]   # primary, fallback
    return [url]
```

and build the candidate list as **host × resolution** instead of resolution alone.

### Ordering: primary `files.d20.io`, fallback `s3.amazonaws.com`

Both hosts are tried either way, so ordering cannot lose an asset — it only decides how
many requests are wasted. The measurement is one-sided:

| | measured |
|---|---:|
| assets probed | 84 |
| 200 on `files.d20.io` | **82** |
| 200 on `s3.amazonaws.com` | **0** |

Putting `s3` first would spend one guaranteed 403 per asset before every success — **2,432
wasted requests** on a Wardens-sized conversion, and a log full of 403 lines that are
expected rather than diagnostic. The renamed host goes first; `s3` stays as the fallback so
the change is safe if Roll20 ever reverts the rename.

Two things worth doing at the same time:

1. **Count the losses.** A per-run summary line (`N assets failed to download`) turns a
   silent degradation into something a conversion log check can fail on. Individual
   warnings scroll past; a total does not.
2. **Reject the placeholder by content.** `imgsrv.roll20.net/?src=…` answers a dead asset
   with **HTTP 200**, a correct content-type and a **10,750-byte** body,
   sha1 `f5c88ae6ead6d209ddf0fdd2a21a755aa6688f5a`. Any recovery path that routes through
   the proxy must content-hash and reject that body, and must reject it *by hash* — the
   placeholder can appear only once in a campaign and then passes a "repeated body" test.

## Test notes

A regression test must not assert "downloads succeed" — that passes against a live CDN
regardless of which host is used. Assert that the **candidate list contains the bare host**
for an `s3.amazonaws.com/files.d20.io/…` input, which is testable offline.
