# B079 - A system summon with empty token art is treated as executable

**Severity:** High
**Status:** Fixed in v1.15.0
**Found:** 2026-08-20 during Tomb of Annihilation v1.14.0 Gate D
**Component:** `src/module_assembly.py` (`localizeExecutableReferences`)
**Related:** B065, B069, B074

## Defect

Module assembly leaves executable UUIDs unchanged when their package equals the game system. That
is valid for availability, but it assumes the resolved system document is usable. dnd5e 5.3.3's
Mage Hand Actor resolves successfully while both its Actor image and prototype-token texture are
empty. A summon creates the Actor and Token, then Foundry cannot draw the Token.

## Evidence

Tomb of Annihilation held 42 source profiles (21 embedded Actor spells and 21 standalone Items)
pointing to `Compendium.dnd5e.monsters.Actor.zwT2WjWo7cTm2631`; Adventure projection duplicated
those 42 references. Gate D created the expected Mage Hand token, but the client emitted twice:

```text
Error: Requested texture path is empty.
```

Localizing the one Actor with a non-empty hand icon and rewriting all 42 source profiles (84 after
Adventure projection) removed the errors; all three sampled Mage Hand workflows then passed.

## Fix contract

- Qualify executable system Actor targets before exempting them from localization: the document,
  Actor image, and prototype-token texture must be usable.
- When art is unusable, clone the target locally and derive a non-empty token image from the
  invoking Item or an explicit policy; otherwise fail with the exact UUID instead of shipping a
  runtime error.
- Rewrite every mechanically affected duplicate to one deterministic local Actor.
- Preserve source ID, summon origin, profile ID, and Always-for-Owner token-name policy.

## Regression coverage required

Cover a valid system summon, a null-image system Actor, duplicate profiles across Actor and Item
packs, one local clone, rewritten UUIDs, token creation without console errors, and unresolved
profile failure.

## Resolution

Module assembly carries the nearest invoking Item image while scanning executable references.
System Actor targets with usable Actor and prototype-token art remain external. Unusable targets
clone once into the local Actor pack, fill missing Actor/token art from the invoking Item, retain the
source ID, rewrite every profile, and use Always for Owner. Missing donor or fallback art aborts
with the exact UUID. `tests/test_module_assembly.py` covers valid, duplicate, and fail-closed paths.