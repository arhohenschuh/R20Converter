# B106 - Macros download and ship the Roll20 brand icon

**Severity:** Moderate
**Status:** Fixed (v1.15.15)
**Found:** 2026-09-03 during owner UAT of *Tyranny of Dragons* 1.2.0-rc.1
**Component:** `src/entities/macros.py`
**Related:** B065, B088

## Defect

The first converted Macro downloaded the icon of the Roll20 Android application from a hardcoded
Google-hosted URL. Every Macro then referenced that downloaded image. This added a network request
to conversion, shipped a third-party brand logo that did not represent the Macro's function, and
made the output depend on a remote body outside the source export.

The exact *Tyranny of Dragons* rc.1 module referenced one 14,410-byte WebP logo from all 11 Macros
and their Adventure projection. Owner UAT replaced those references with semantic Foundry icons.
The first repair left the now-unreferenced logo in the archive, which independent review correctly
rejected; the corrected module removed it and strengthened its reverse-reference oracle.

## Cause

`Macros` cached `_img_path`, while `Macro.__init__` populated that cache by calling
`downloadResource()` with a hardcoded `lh3.googleusercontent.com` Roll20 application-icon URL.
The fallback already used Foundry's native `icons/svg/dice-target.svg`, but only after the remote
download failed. A successful download therefore selected the undesirable path.

## Fix contract

- Use `icons/svg/dice-target.svg` as the deterministic default for every source Macro.
- Do not request, download, copy, or reference a remote brand icon during Macro construction.
- Preserve source Macro identity, command, ownership, author, scope, ordering, and projection.
- Keep campaign-specific semantic icon selection as explicit downstream content policy.

## Regression

The focused constructor test replaces `Macro.downloadResource` with a function that fails the test
if called, then requires the emitted `img` to equal `icons/svg/dice-target.svg`. Tagged v1.15.14
fails this control by attempting the download; v1.15.15 passes without invoking it.