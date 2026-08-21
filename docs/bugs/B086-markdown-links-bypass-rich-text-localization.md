# B086 - Markdown links bypass rich-text localization

**Severity:** High
**Status:** Fixed in v1.15.2
**Found:** 2026-08-20 during Eberron Setting v1.0.0 Gate A
**Component:** `src/entities/base.py` (rich-text links)
**Related:** B065, B071, B075

## Defect

Journal, Actor, and Item rich text runs HTML anchor localization only. Roll20 source can embed
Markdown `[label](target)` syntax inside those HTML fields, so internal Journal links never reach
`replaceEntityLinks()` and web links render as literal Markdown in Foundry.

Eberron Setting Gate A measured 240 occurrences including the Adventure projection, or 120 source-
pack links. Labels include HTML entities and inline spans; targets include Roll20 Journal URLs and
`app.roll20.net` compendium pages.

## Fix contract

- Convert non-image Markdown links to ordinary HTML anchors before existing link handling.
- Preserve label markup and safely quote ampersands and double quotes in targets.
- Allow existing Roll20 Journal anchors to become local UUIDs.
- Keep unresolved web/compendium targets as readable HTML links.
- Do not reinterpret Markdown image syntax.

## Resolution

`Entity.replaceMarkdownLinks()` runs at the start of `replaceEntityLinks()`. Focused coverage proves
an obfuscated Markdown Journal label becomes the correct module Journal UUID; the existing HTML
link suite remains green.