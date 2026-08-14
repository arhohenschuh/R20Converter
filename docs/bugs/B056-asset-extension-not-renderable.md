# B056 — asset extension is taken from the URL, so Foundry will not render the file

**Status:** partially fixed in v1.7.7 (`downloadResource`); **completed in v1.8.1** (`copyZipFile`)
**Severity:** high — the asset converts, is written to disk, and is silently never drawn
**Component:** `src/entities/base.py` → `Entity.downloadResource` **and** `Entity.copyZipFile`
**Found:** 7 Aug 2026, chasing a map that "did not import" on *Wardens of the North*

## Symptom

A scene converts, its tile exists, the image file is on disk at the right path and every
existing check passes — G07, G09 and G10 all read green, because the file is present and
non-empty. The map simply does not draw. From inside Foundry the scene looks like it failed
to import.

## Cause

`downloadResource` named the stored file after the extension **advertised by the Roll20 URL**:

```python
splitext = os.path.splitext(url)
extension = splitext[1].split("?")[0]
```

Two things go wrong with that.

**1. Only a `?` fragment is stripped.** Roll20 also serves cache-busters after `&`, so a URL
ending `original.svg&cb=5` produced a file literally named `….svg&cb=5`. The comment directly
above this code already noted that a trailing fragment "break[s] FVTT which doesn't recognize
the URL as having a valid extension" — the `&` form was simply missed.

**2. The advertised extension is not always renderable.** Foundry only draws paths whose
extension is in `CONST.IMAGE_FILE_EXTENSIONS`:

```
apng, avif, bmp, gif, jpeg, jpg, png, svg, tiff, webp
```

`.jfif` is not in that list. It is an ordinary JPEG container, Roll20 serves it happily, and
Foundry drops it without a word.

## Measured

Across the 11 archived exports:

| extension written | files | exports |
|---|---:|---|
| `.svg&cb=5` | **52** | Storm over Savage Frontier (48), Curse of Strahd (4) |
| `.jfif` | 2 | Wardens of the North |

> ⚠ **Re-measured 14 Aug 2026, and this table was wrong.** It counted the two worlds
> under repair at the time, not the fleet. Scanning every archived export ZIP for members
> whose extension is outside `CONST.IMAGE_FILE_EXTENSIONS`, or that carries a `&` fragment:
>
> | campaign | affected zip members |
> |---|---:|
> | Dungeon of the Mad Mage | 74 |
> | Storm over Savage Frontier | 48 |
> | Lost Mine of Phandelver | 11 |
> | Curse of Strahd | 4 |
> | Wardens of the North | 2 |
> | **total** | **139** |
>
> *Dungeon of the Mad Mage* and *Lost Mine of Phandelver* are both shipped modules and
> appear in neither the original table nor the "only newly converted worlds benefit" note.

The two `.jfif` files are the *Lakeside* map and its thumbnail, sitting in
`worlds/wardens-of-the-north-season-3/assets/tiles/`.

Worth recording: **the extension did not match the content either.** Reading the magic bytes
of the two files gave

| file | size | magic | actually |
|---|---:|---|---|
| `2a8ccf26….jfif` | 5.5 MB | `89 50 4e 47` | **PNG** |
| `abe319f4….jfif` | 11 KB | `ff d8 ff e0 … JFIF` | JPEG |

so a blanket `.jfif → .jpg` rename of the files on disk would have put PNG bytes in a `.jpg`.
Browsers sniff content and would still draw it, but the name would be a lie. Anything
repairing existing worlds must read the magic bytes per file rather than trust either the
extension or the URL.

## Fix

The derivation moves into `Entity.assetExtension`, which keeps only the leading alphanumeric
run of the extension — dropping `?…` and `&…` alike — and translates the aliases Roll20
serves that Foundry does not list:

```python
EXTENSION_ALIASES = {"jfif": "jpg", "jpe": "jpg", "jif": "jpg", "jfi": "jpg", "tif": "tiff"}
```

`RENDERABLE_EXTENSIONS` records the client's accepted set alongside it, so the next person
does not have to go digging in `common/constants.mjs`.

## Notes

Fourth instance of the same shape as B049/B053/B055: **the pipeline reported success because
every check it had was satisfied.** The file existed, was non-empty, was referenced and
resolved — the one thing nobody asked was whether the client could actually draw it. A
renderability check on asset extensions belongs in Gate A; G09 proves a reference resolves, not
that it displays.

Only newly converted worlds benefit. Existing worlds need the files renamed by content and
their documents rewritten; for Wardens that is 2 files, and Storm/Curse of Strahd carry none
of the 52 `.svg&cb=5` (they never reached the converted worlds, which is a separate question).

## The fix was half a fix (found 14 Aug 2026, shipped in v1.8.1)

`assetExtension` was wired into `downloadResource` only. That is the path taken when an asset
is **missing** from the export ZIP. Every asset that is **present** — the overwhelmingly common
case, and the source of all 139 measured files — goes through `copyZipFile`, which carried its
own copy of the original derivation:

```python
splitext = os.path.splitext(url)
extension = splitext[1].split("?")[0]          # unchanged by the 1.7.7 repair
```

The reason it survived review is that one variable was doing two jobs. `extension` names the
file **written to disk** *and* is the fallback used to find the member **inside the ZIP**.
Those must not be the same value: R20Exporter deliberately names its zip members from the raw
URL (its ADR-003, so that a canvas-re-encoded PNG is still findable), so the lookup has to keep
`.jfif` and `&cb=5` while the stored file must not. Normalising both would have turned a
silent non-render into a hard `Cannot find file … in Zip` miss.

`copyZipFile` now keeps `zip_extension` (raw, for the lookup) and `dest_extension`
(`assetExtension`, for disk) apart. Tests: `tests/test_asset_extension.py`,
`TestAssetsCopiedOutOfTheZip` — proved able to fail against the pre-fix derivation before
being trusted.

**Gate debt this exposes, and which is still open.** Gate A's `qa-gate.mjs` lists `jfif` in its
`ASSET_PATH` regex as an *accepted* asset extension, so it cannot catch this class even now.
The renderability check this record asked for in August was never added. Until it is, the only
instrument is the offline ZIP scan and the exporter's new `renderable` flag.

