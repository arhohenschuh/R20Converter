# B097 - Asset deduplication keys by URL instead of file content

**Severity:** Major
**Status:** Open owner-pickup request
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
