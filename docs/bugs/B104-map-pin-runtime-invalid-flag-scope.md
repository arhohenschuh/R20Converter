# B104 - Map Pin runtime calls `getFlag` with an invalid package scope

**Severity:** High
**Status:** Fixed (v1.15.13)
**Found:** 2026-08-28 during live Scene acceptance of *Waterdeep: Dungeon of the Mad Mage*
**Component:** `templates/map-pin-notes.js`

## Defect

Every rendered Scene containing converted Map Pins raises:

```text
Flag scope "R20Converter" is not valid or not currently active
```

The exhaustive Wall run still matched and rendered all 28 Scenes and all 87,780 Walls, but captured
52 page errors across the 26 Pin-bearing Scenes. Pin visibility and click handling could therefore
not be accepted.

## Cause

Converted Notes retain their complete source payload at `flags.R20Converter.mapPin`. The runtime
read it with `Document#getFlag("R20Converter", "mapPin")`. Foundry validates the first argument as
an active package ID; `R20Converter` is a historical data namespace, not the generated module ID,
so the API throws even though the stored payload is present and valid.

The synthetic tests returned a payload from `getFlag` for that scope and therefore modeled behavior
Foundry rejects.

## Resolution

Read the existing structured payload directly from `document.flags.R20Converter.mapPin`. This is a
runtime-only fix: no Note IDs, source payloads, or compendium data need migration. Every regression
harness now provides the structured flag and throws if the runtime calls `getFlag`, while retaining
coverage for exact-heading activation, click-only behavior, hidden-player denial, hidden-GM
visibility, inherited `isVisible`, and ordinary Notes.

The focused Python 3.8 runtime suite passes 3/3 and the complete shipping suite passes 972/972.
The live RED run matched and rendered **28/28 Scenes and 87,780/87,780 Walls** but captured
**52** invalid-scope page errors. With the fixed runtime copied byte-for-byte, the identical run
passes with zero console/page errors. The physical Pin gate also passes: **1,620** world Pins,
**92** Level 1 Pins, no visible hover, one click opening the exact **38. Secret Tunnel** anchor,
and zero visible/rendered Pins for a temporary player; ownership and the player are restored and
removed during cleanup.