# B087 - Relative HTML images have no package root

**Severity:** High
**Status:** Fixed in v1.15.2
**Found:** 2026-08-20 during Eberron Setting v1.0.0 Gate A
**Component:** `src/module_assembly.py` (embedded HTML art)
**Related:** B065, B070, B080

## Defect

Module assembly internalizes HTTP and `modules/...` image sources but ignores bare relative paths.
Foundry resolves those paths against the data root, outside the module, so they are nonportable even
if a developer machine happens to contain matching files.

Eberron Setting contains one source Journal page with ten references across six
`0_DnD_EFA_*.jpg` names; its Adventure duplicates those ten. Exhaustive ZIP and retained-work
search found no matching bytes, so the source art is unavailable rather than merely misaddressed.

## Fix contract

- For a relative HTML image path, search source ZIP members by exact path or unique suffix.
- Copy and rewrite a unique nonempty match through the existing deduplicating asset pipeline.
- Abort on ambiguous matches.
- If no source bytes exist, remove the complete image tag, log distinct paths and stripped tags,
  and preserve surrounding prose.
- Keep external URL failures fail-closed and explicit package paths unchanged.

## Resolution

Module assembly now distinguishes external, explicit-package, and undeclared relative image paths.
Unique ZIP members are copied; missing relative tags are stripped and counted; ambiguous matches
abort. Focused controls cover recovery, missing art, ambiguity, placeholders, and external failures.