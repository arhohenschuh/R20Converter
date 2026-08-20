# B070 - Zero-byte ZIP asset is accepted

**Severity:** High
**Status:** Fixed in v1.14.0
**Found:** 2026-08-20 during frozen LMoP qualification

`copyZipFile()` treated a ZIP member as successful whenever it existed. A zero-byte member was
written locally and returned as a valid path, so the existing URL/CDN fallback never ran. Foundry
then resolved the path but could not render it.

The copier now reads the member before writing, rejects an empty body, and retries through
`downloadResource()` when the source URL exists. The downloader also rejects an HTTP 200 with an
empty body and continues through its host/resolution candidates. Scene thumbnail writes now use a
temporary file, choose output format from the destination extension, and convert RGBA sources to
RGB before JPEG output. `tests/test_asset_extension.py`, `tests/test_base_download.py`, and
`tests/test_scene_thumbnail.py` cover all three producers and require no zero-byte destination to
survive.