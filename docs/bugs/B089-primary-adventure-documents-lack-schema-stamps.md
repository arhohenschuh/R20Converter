# B089 - Primary Adventure documents lack schema stamps

**Severity:** High
**Status:** Fixed in v1.15.2
**Found:** 2026-08-20 during Eberron Setting v1.0.0 package preflight
**Component:** Folder, JournalEntry, Macro, Scene, and RollTable emitters
**Related:** B043, B065, B088

## Defect

Actor and Item emitters attach `_stats`, but five other primary document owners do not. Module
assembly copies those documents into the native Adventure unchanged. The package therefore claims
Foundry 14 compatibility while hundreds of primary Adventure documents have no
`_stats.coreVersion` or `systemVersion`.

The reviewed Eberron Setting candidate measured 886 unstamped Adventure documents: 24 Scenes,
517 Journals, 170 source RollTables, 88 Folders, and 87 Macros. The archive verifier correctly
blocked packaging before any ZIP was created.

## Fix contract

- Add the standard `Entity.documentStats()` block to every Folder, JournalEntry, Macro, Scene, and
  RollTable primary document.
- Emit core version 13 and dnd5e system version 5.3.3, matching the converter's existing Actor/Item
  contract and package compatibility allowlist.
- Ensure the native Adventure receives the same stamped copies.
- Do not fabricate stamps on external donor documents; preserve their measured source versions.

## Regression coverage required

Focused constructors for all five affected document types must assert core 13 and dnd5e 5.3.3.
The full converter suite and package schema verifier must remain green.

## Resolution

All five emitters now include `self.documentStats()` in their primary document dictionaries.
Focused tests cover each type and the shipping suite passes with the added assertions.