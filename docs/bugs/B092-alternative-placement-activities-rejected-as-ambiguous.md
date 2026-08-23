# B092 - Alternative placement activities are rejected as ambiguous

**Severity:** High
**Status:** Fixed in v1.15.4
**Found:** 2026-08-23 during *Dead in Thay* v1.15.3 reconversion
**Component:** `src/entities/items.py` (`_mergeSpellConsumption`, `_validateResourceContract`)
**Related:** B077, B082, B083

## Defect

A limited innate spell can expose several complete casting activities because the caster chooses
one placement shape. Every choice must spend the same Item-use pool, but v1.15.3 required exactly
one donor primary and exactly one positive Item-use consumer. It therefore treated legitimate
alternatives as duplicate consumers and aborted conversion.

The Efreeti's **Wall of Fire** is 1/day. The current Beyond5e donor contains:

- `saveWallOfFireII`, **Place Wall**, a save activity with a `wall` template;
- `addPlaceRing1III`, **Place Ring**, a save activity with a `cylinder` template;
- `addDamage2IIIIII`, a non-casting follow-up damage activity.

Both placement activities consume a spell slot in the ordinary donor because either one is a
complete cast. During innate conversion both must instead consume one use from the Efreeti's
single 1/day Item pool. Version 1.15.3 raised `Cannot select one primary donor activity` before
module assembly.

## Evidence

- Immutable source:
  `TotYP_Dead in Thay_R20Export-1.0.1.zip`, 659,653,839 bytes,
  SHA-256 `C10DB5C01547D862A54BA4CEA0B89D0177D48BD61424ABC6B41B9265F16E90BC`.
- Source character ID: `-Kd2gu13VG0XQWFSbNi4`; source trait:
  `repeating_npctrait_-Kd2guD4tHA-MHqBDTu1_desc`.
- Emitted Actor ID: `YWI2NDEwZmY3Y2Iw`; Item ID: `YWMxMmQ5YzQ1YjBh`.
- Semantic adjudication:
  `D:\Automation_Local\Two_Channel\tftyp-dead-in-thay\release\1.1.2-reconversion-001\reports\semantic-adjudication.json`.
- Accepted projection proves both Actor-pack and Adventure copies carry the 1/day pool and both
  Item-use consumers:
  `reports\wall-of-fire-projection.json`.
- Current donor confirmation: Beyond5e `1.1.13-rc.5`, repository commit
  `b7396aaa128209e69498ff230dde1d2f9af37e8c`.

## Required handling

- Preserve every explicit placement choice when the activities represent mutually exclusive ways
  to perform one cast.
- Copy the source Item-use target to every placement choice and disable spell-slot consumption on
  unrelated follow-up activities.
- Keep ordinary same-type multi-activity ambiguity fail-closed.
- Do not classify transform, concentration, damage, or unnamed duplicate activities as placement
  alternatives.

## Resolution

The merge and validation boundaries now recognize a bounded alternative-placement group: at least
two same-type slot-consuming activities, each explicitly named `Place ...`, each carrying a
concrete and distinct template type. Every group member receives the same Item-use target. All
other primary selection and exactly-one-consumer rules remain unchanged.

The positive regression reproduces Wall of Fire's Wall/Ring choices and preserves the non-casting
Damage activity. The pre-existing two-save ambiguity control remains red without the fix and green
only when conversion still aborts.