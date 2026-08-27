# B102 - Roll20 Map Pins are omitted

**Severity:** High
**Status:** Fixed (v1.15.11)
**Found:** 2026-08-27 during owner inspection of *Waterdeep: Dungeon of the Mad Mage*
**Component:** `src/entities/scenes.py`, `src/module.py`, `templates/map-pin-notes.js`

## Defect

R20Exporter 1.4.1 exposes Roll20 Map Pins as `pages[].pins`, but R20Converter 1.15.10 ignores that
collection. Converted Scenes therefore contain no corresponding navigation objects even when the
source map has complete area keys.

The Pin-based *Dungeon of the Mad Mage* campaign contains 1,620 unique Pins on 26 of 29 pages.
Every Pin links to a Handout and heading, all 1,620 references close, and Level 1 alone contains 92
Pins. The omission removes the module's primary map-to-area navigation while leaving otherwise
plausible Scenes, so ordinary graphics and Journal count checks do not detect it.

## Cause

Scene conversion handled graphics, text, paths, doors, lights, and tokens but had no owner for the
new `pins` collection. Foundry's native Note interaction also opens linked Journals on double click,
whereas the source workflow requires click-only exact-heading navigation and per-Pin visibility.

## Required handling

- Emit one native Scene Note for every valid source Pin.
- Resolve the linked Handout to its JournalEntry and text JournalEntryPage; fail closed if either is
  missing instead of silently dropping the Pin.
- Preserve coordinates, scale, source label, shape, colors, visibility, and the complete original
  Pin payload.
- Open the exact table-of-contents heading on one click and suppress duplicate double-click
  activation.
- Disable Pin hover interaction without changing ordinary Note behavior.
- Show hidden Pins to GMs but not players; keep `visibleTo: all` Pins available subject to native
  Journal permission.
- Package the runtime script only in modules that contain converted Map Pins.

## Candidate resolution

`Scene.createMapPinNotes()` now emits linked Notes with deterministic IDs, scaled coordinates,
package-owned SVG marker textures, and `flags.R20Converter.mapPin` containing the complete source
record. Target resolution requires a Handout and text page.

The conditional runtime script patches Foundry's Note object only when the module contains Pins.
It resolves exact heading text through `JournalEntryPage.toc`, falls back to
`slugifyHeading()`, and shares one debounced activation path across Foundry's single- and
double-click callbacks. Pin `_canControl()` delegates to view permission so one click is reachable
in normal play, while native control still runs when a GM can select the Note. Hover callbacks
accept Foundry's pointer-state transition without setting the Note's hover state, so Pins remain
clickable without showing a tooltip. Source visibility is applied through both `isVisible` and
`_canView()`. Original methods and getters remain in force for ordinary Notes.

The behavior is grounded in the installed Foundry 14.367 Note, PlaceableObject,
MouseInteractionManager, and JournalEntryPage implementations. Independent QA round 1 rejected
activation through `_onClickLeft()` alone because Foundry binds that callback to native control
permission, and rejected returning `false` from Pin hover callbacks because it prevents the pointer
state from reaching click handling. The corrected permission-map regression proves player and GM
single-click reachability, hidden-player denial, native GM control, accepted hover state transitions
without a visible tooltip, and one activation for a double-click gesture.

Tagged v1.15.10 fails the native-Note and runtime regressions 2/2; the corrected candidate passes
the focused 6/6 suite and the complete shipping Python 3.8 suite at 971/971. The validated 1.4.1
DotMM archive contains 1,620 unique Pins, 1,620 closed Handout references, 29/29 matching page JSON
records, and zero Pin integrity findings.