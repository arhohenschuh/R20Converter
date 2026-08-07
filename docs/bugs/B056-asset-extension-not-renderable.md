# B056 — asset extension is taken from the URL, so Foundry will not render the file

**Status:** fixed in v1.7.7
**Severity:** high — the asset converts, is written to disk, and is silently never drawn
**Component:** `src/entities/base.py` → `Entity.downloadResource`
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
