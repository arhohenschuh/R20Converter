# ADR-001: Reproducible builds and visible errors

- **Status**: Accepted
- **Date**: 2026-07-25
- **Supersedes**: —
- **Superseded by**: —

> This ADR is written retroactively to document the decision already implemented in
> commit `196e8d8` ("Harden build reproducibility and error visibility").

## Context

R20Converter had no dependency manifest. The README listed dependency *names*
(`requests`, `pillow`, `python-slugify`, `matplotlib`, `eel`) but no versions, so
a fresh checkout resolved to whatever was current on PyPI that day. Several of
those packages have since released breaking major versions, meaning a build could
silently stop working with no change to our own source.

The repository also contained two competing build descriptions:

- `setup.py`, using **cx_Freeze**, referenced by `build_windows.bat` and
  `build_mac.sh` — the path actually used.
- `R20Converter.spec`, a **PyInstaller** spec, unreferenced by anything and
  containing a hardcoded `pathex` pointing at the original author's machine.

A newcomer could not tell which one was real.

Finally, compendium pack loading in `R20Converter.loadDnD5ePacks()` and
`loadSystemPacks()` used `except: pass`. When a pack failed to load — the single
most common cause of "my character sheets are empty" reports — the user saw
nothing at all.

## Decision

1. Add `requirements.txt` pinning **exact** versions of every runtime and build
   dependency, verified to build and run together. Document the one non-pip
   requirement (the Electron runtime for the Windows build) as a comment in the
   same file, since it is part of the same reproducibility contract.
2. Declare `setup.py` / cx_Freeze the single supported build path, and mark
   `R20Converter.spec` as deprecated in a header comment rather than deleting it,
   to avoid breaking anyone's muscle memory without explanation.
3. Replace silent `except: pass` around pack loading with logged warnings that
   name the pack and include the exception text.

## Alternatives considered

- **Loose version ranges (`>=`)** — rejected. The failure mode we are fixing is
  precisely "an upstream release broke us"; ranges do not prevent that.
- **Deleting `R20Converter.spec`** — rejected at the time in favour of an
  explicit deprecation notice, which teaches rather than merely removes.
- **Leaving pack-load failures silent** — rejected. Silence here is the direct
  cause of the most frequent user-reported symptom.

## Consequences

- A checkout plus `pip install -r requirements.txt` reproduces a known-good
  environment.
- Dependency upgrades are now deliberate, reviewable commits.
- Users see actionable warnings when compendium packs cannot be read.
- Pins must be refreshed periodically; without CI this is manual. ADR-004
  addresses that gap.
