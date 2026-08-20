# B080 - Roll20's dead-image placeholder is stored as valid art

**Severity:** High
**Status:** Fixed in v1.15.0
**Found:** 2026-08-20 during Tomb of Annihilation v1.14.0 qualification
**Component:** `src/module_assembly.py` and `src/entities/base.py` (asset acquisition)
**Related:** B048, B049, B065, B070

## Defect

Roll20's image proxy answers some dead assets with HTTP 200 and a fixed 10,750-byte placeholder.
The asset pipeline rejects empty files but does not identify this known body, so module assembly
deduplicates and stores it under content-derived local paths. Every HTML reference resolves and is
non-empty while still displaying the dead-image placeholder.

## Evidence

Fresh Tomb of Annihilation v1.14.0 output contained 29 stored files with SHA-1
`f5c88ae6ead6d209ddf0fdd2a21a755aa6688f5a`. They appeared in 76 complete HTML `<img>` tags:
38 in source Actor biographies and 38 in the Adventure projection. No reference occurred outside
a complete removable image tag.

The missing original images are source defects. Accepting a known Roll20 placeholder body as
successful art is the converter defect.

## Fix contract

- Detect the known placeholder by exact body hash after every ZIP/HTTP acquisition path.
- Treat it as an unavailable asset, never as a successful non-empty file.
- Remove a complete dead HTML `<img>` tag when no real candidate can be recovered; fail closed for
  structural image fields that cannot safely be omitted.
- Report placeholder URLs, references, stripped tags, and stored-file count separately from generic
  download failures.
- Do not classify arbitrary dead source images as this bug without the exact signature.

## Regression coverage required

Cover proxy and direct URL forms, the exact placeholder body, a same-size non-placeholder control,
ZIP and HTTP paths, complete-tag stripping, structural-field failure, and zero stored placeholder
files.

## Resolution

`isRoll20Placeholder()` requires the exact 10,750-byte size and full SHA-1. HTTP, ZIP, and external
module reads reject it before writing. Module HTML handling removes the complete affected `<img>`
tag and reports distinct URLs/references/tags with zero stored files; structural fields propagate a
typed failure. Asset and assembly tests cover proxy/direct, same-size negative, fallback, stripping,
and structural failure, while immutable ToA evidence confirms the retained real body is detected.