# B105 - Map Pins obscure Tokens and cannot be moved normally

**Severity:** High
**Status:** Fixed (v1.15.14)
**Found:** 2026-08-28 during owner inspection of *Waterdeep: Dungeon of the Mad Mage*
**Component:** `templates/map-pin-notes.js`

## Defect

Converted map Pins render in Foundry's native Notes layer at z-index 800, above the Token layer at
z-index 200. Large Pin icons therefore hide Tokens and intercept their pointer interactions. The
click-only runtime also consumes the same single-click gesture Foundry uses to select Notes, while
the converted Notes remain locked, so a GM cannot conveniently reposition them.

The same inspection found that Foundry's Scene directory defaults to alphabetical client sorting.
That mode displays `Level 10` before `Level 2` even when converted Scene Folders correctly store
manual numeric sort values.

## Cause

Native Notes are intentionally a foreground interface layer. Converted Roll20 Pins need Note
documents and Note interaction behavior, but they are map annotations and should visually sit
below Tokens. The initial runtime changed click and hover behavior only; it did not provide a
separate rendering layer or an explicit editing mode.

Foundry stores top-level directory sorting in the client-scoped
`core.collectionSortingModes` setting. Emitting manual Folder sort values is necessary but does
not override a client's alphabetical Scene-directory mode.

## Resolution

Render only converted Pin placeables in a dedicated interface container at z-index 199 while
retaining their logical Notes-layer registration, visibility checks, quadtree membership, native
drag behavior, and teardown lifecycle. Ordinary Journal Notes remain in the native layer at
z-index 800.

Add a GM-only **Edit Map Pins** Scene control. Enabling it unlocks converted Pins in the current
Scene and restores native hover, selection, and drag handling; disabling it relocks the Pins,
releases their controls, and restores click-only exact-heading navigation. Players never receive
the control. Select Foundry's native manual Scene-directory mode when the conditional Pin runtime
loads, preserving the converter's stored Folder sort values.

The focused Python 3.8 runtime suite passes 4/4, including z-order, Notes registration, quadtree,
unlock/relock, edit-mode click routing, Player control absence, teardown, and manual sorting. A
real role-1 Player loaded all 26 Pin-bearing DotMM Scenes: all 1,620 Pin placeables reported zero
visible, rendered, viewable, controllable, and hovered objects. A forced-visible negative control
detected exactly one leak, and all temporary permissions and the temporary Player were removed.