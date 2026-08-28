# B103 - Map Pin runtime assumes `isVisible` is an own property

**Severity:** High
**Status:** Fixed (v1.15.12)
**Found:** 2026-08-28 during Foundry 14.367 migration acceptance of *Waterdeep: Dungeon of the Mad Mage*
**Component:** `templates/map-pin-notes.js`

## Defect

The conditional Map Pin runtime throws during Foundry's `init` hook:

```text
Cannot read properties of undefined (reading 'configurable')
```

All nine compendium packs still load, which makes an offline conversion appear complete, but the
runtime patch never installs. Converted Pins therefore have no enforced GM visibility, no
click-only behavior, and no exact-heading activation.

## Cause

The runtime called `Object.getOwnPropertyDescriptor(CONFIG.Note.objectClass.prototype,
"isVisible")`. Foundry may configure a Note subclass whose `isVisible` getter is inherited from
the core Note class. The own-property lookup returns `undefined`, and constructing the replacement
descriptor immediately dereferences it.

The synthetic B102 tests defined the getter directly on their configured Note class, so they did
not model this valid Foundry inheritance shape.

## Resolution

Walk the configured Note prototype chain until the native `isVisible` descriptor is found. Require
an actual getter and fail with a focused error if Foundry removes that contract. Install the
Pin-specific getter on the configured subclass while continuing to call the native inherited
getter for ordinary Notes and visible Pins.

The regression uses a configured Note subclass with no own `isVisible` property and a core parent
that owns the getter. It proves successful init, an own patched getter on the configured class,
ordinary Note visibility, hidden-player denial, and hidden-GM visibility.

The focused runtime suite passes 3/3 and the complete shipping Python 3.8 suite passes 972/972.
