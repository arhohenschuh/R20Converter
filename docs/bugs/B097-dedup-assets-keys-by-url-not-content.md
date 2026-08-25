# B097 - Asset deduplication keys by URL instead of file content

**Severity:** Major
**Status:** Fixed in v1.15.9
**Found:** 2026-08-25 during official-versus-converted *Shattered Obelisk* review
**Component:** `src/entities/base.py` (`getDestinationPaths`, `downloadResource`, `copyZipFile`)
**Related:** B048, B049, B056, B070, B080

## Request

Make `--dedup-assets` a byte-identity contract rather than a URL-identity naming policy, and derive
the stored image extension from the encoded body before exposing the final path.

## Evidence

The converted *Shattered Obelisk* 1.4.1 asset tree contains 1,556 files but only 1,252 unique
SHA-256 bodies. The 304 extra copies waste 119,151,571 raw bytes even though conversion used
`--dedup-assets`. Four image names also disagree with their bodies: three `.jpg` paths contain PNG
and one `.png` path contains WebP. The official comparison tree has 725 files, 725 unique bodies,
and zero extension/signature mismatches.

The controlling code hashes `url` in `getDestinationPaths()`. Identical bytes reached through
different URLs therefore receive different names, while an incorrect URL suffix survives even
when the downloaded or ZIP body encodes another format.

An independent *Tomb of Annihilation* 1.1.4 measurement reproduced the defect at larger scale:
2,198 assets contain only 1,661 unique bodies. Its 537 extra copies form 352 duplicate groups and
waste 163,300,070 bytes; 81 duplicate files cross the old root/Actor/Tile type directories. The
11,716,084-byte Parchment Battle Map is named `.jpg` but begins with the exact PNG signature and
hashes to `3AF437B49A0C8A5663439FE590A687202BB944559C20A1BCDD3CDE602F315FD2` in both the immutable
Roll20 export and converted module.

## Acceptance criteria

- Hash acquired bytes before final placement and reuse one package-owned file for equal bodies.
- Detect PNG, JPEG, WebP, GIF, and other supported media from signatures; reject unknown bodies.
- Choose the final extension from the encoded format, then return that exact reference to the
  caller. Do not silently transcode.
- Preserve URL/path provenance separately for diagnostics; it must not define byte identity.
- Treat hash collision, target-path collision, empty body, and unsupported format as explicit
  failures or retained-source decisions.
- Add tests for two URLs with equal bytes, one URL with changed bytes, mislabeled PNG/JPEG/WebP,
  ZIP and network acquisition, and reference reuse across Actor/Journal/Scene surfaces.
- Emit conversion totals for acquired files, unique bodies, reused references, duplicate bytes
  avoided, and signature corrections.

## Candidate resolution

Both ZIP and network acquisition now inspect encoded bytes before final placement. Recognized PNG,
JPEG, WebP, GIF, BMP, TIFF, and AVIF bodies override an advertised suffix without transcoding;
unrecognized media retain the source-extension decision and are counted in telemetry.

With `--dedup-assets`, final names use the acquired body SHA-256 in one package-wide namespace, so
equal bytes reuse one file across Actor, Journal, Scene, and other categories even when their URLs
differ. An occupied content-hash path is streamed and verified before reuse; different bytes abort
instead of being silently aliased. Non-deduplicated output keeps its existing named layout.

The conversion log now emits acquired references, unique bodies, reused references, duplicate
bytes avoided, signature corrections, and retained source extensions. Regression coverage includes
ZIP and network acquisition, equal and unequal bodies, cross-category reuse, PNG/JPEG/WebP and
other supported signatures, source-extension retention, collision rejection, and exact telemetry.
Independent Opus QA passed all 7 targets with zero findings and rejected all 9 negative controls.
The 21-file packet remained byte-identical at lock SHA-256
`23B42F165ADD382203A226A48A20C8BC03BC7F4F04665ABDB24082BF61F870AF`. The final post-review
same-URL/changed-body regression also passes. The combined B097/B100 Python 3.8 suite passes
963/963.
