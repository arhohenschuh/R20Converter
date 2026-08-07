# B054 — a magic AC bonus overwrites the armour's base AC

**Status:** fixed in v1.7.5
**Severity:** high — silently destroys the base AC of every magic armour
**Component:** `src/entities/actors.py` → `addInventoryItem`
**Found:** 6 Aug 2026, while repairing the AC collapse in Wardens / Storm / Dragoncoast

## Symptom

A magic armour converts with an `armor.value` equal to its **magic bonus** instead of its
base AC. Measured in the live worlds:

| actor | item | `armor.value` shipped | should be |
|---|---|---:|---:|
| Sylvaris Rhovan Lockmere | Drachenschutz +2 (Half Plate +2) | **2** | 15 (+2) |
| Edek Djarof | Breastplate "Drachenschutz" +1 | **1** | 14 (+1) |
| Darthoridan Pastina | Elven Chain +1 | **1** | 13 (+1) |

The wearer's AC drops to roughly their Dex modifier plus the bonus. It stays **invisible**
while the armour is unequipped, which is how it survived three published worlds — dnd5e only
derives AC from armour that is actually worn.

## Root cause

Roll20 emits the base AC and the magic bonus as **two separate entries under the same key**
in `itemmodifiers`. Verified in the raw export:

```
Item Type: Medium Armor, AC: 15, AC +2, Stealth:Disadvantage     <- Drachenschutz +2
Item Type: Medium Armor, AC: 14, AC +1                            <- Edek's Breastplate
Item Type: Medium Armor, AC: 13, AC +1                            <- Elven Chain
```

`addInventoryItem` parses that list into a **flat dict**, so the second `AC` clobbers the
first (`src/entities/actors.py`):

```python
for mod in mods.split(","):
    if ":" in mod:
        key, value = mod.split(":", 1)
        modifiers[key.strip()] = value.strip()     # "AC" -> "15"
    elif "+" in mod:
        key, value = mod.split(" +", 1)
        modifiers[key.strip()] = "+" + value       # "AC" -> "+2"   *** overwrites ***
...
armor = modifiers.get("AC", 0)
...
equipment.ac = int(armor)                          # int("+2") == 2
```

`int("+2")` succeeds, so the `except ValueError` guard never fires and nothing is logged.

`ItemEquipment.getDict` already emits an `armor.magicalBonus` field — hardcoded to `None` —
and `ItemEquipment.MAGICAL_BONUS` already exists as a type constant. The destination for the
bonus is present and unused.

## Second facet — non-armour AC bonuses become armour

The same block treats *any* item with a non-zero AC modifier as equipment:

```python
if item_type in ["Light Armor", "Medium Armor", "Heavy Armor", "Shield"] or armor != 0:
```

so a ring or a cloak that grants +1 AC is converted into an equipment item with
`armor.value = 1`, and `armor_type` (`"ring"`, `"wondrous"`, `"melee"`) matches none of the
branches, leaving it as `clothing`. dnd5e grants **no AC at all** for these, because the
bonus belongs on `system.attributes.ac.bonus` via an effect, not on an item's base value.

Across the three exports, 7 distinct items carry a separate AC bonus — **4 of them are not
armour**:

| actor | item | modifiers |
|---|---|---|
| Darthoridan Pastina | Staff of Defense | `Item Type: Melee Weapon, AC +1` |
| Darthoridan Pastina | Cloak of Protection | `Item Type: Wondrous Item, AC +1, Saving Throws +1` |
| Torden Lynn | Ring of Protection | `Item Type: Ring, AC +1, Saving Throws +1` |
| Copy of Darthoridan | Staff of Defense | `Item Type: Melee Weapon, AC +1` |

This is consistent with — and is the most likely explanation for — **Darthoridan finishing at
AC 19 against a character sheet that reads 20**: his Elven Chain base was destroyed by facet
one, and his Cloak of Protection / Staff of Defense +1 cannot contribute under facet two.
Shipped at 19 by explicit ruling in Wardens 2.0.5; recorded here as the probable cause rather
than a proven one, since it was not re-measured in the live world.

## Not a defect: bonuses Roll20 never recorded

Thormir Dunkelbier's "Leather Armor Steinhaut +1" exports as `Item Type: Light Armor, AC: 11`
— **no bonus entry at all**. `armor.value = 11` is a faithful conversion; the +1 exists only
in the item's name. No converter change can recover it, and it should not be inferred from
the name. (This is why Thormir's sheet reads 14 while the world computes 16 — see the Storm
1.0.10 FIXLOG.)

## Proposed fix

1. **Accumulate instead of overwrite.** Collect repeated keys into a list, or special-case
   `AC`: an entry of the form `AC: N` is the base, `AC +N` / `AC -N` is a bonus.
2. **Route the bonus to `armor.magicalBonus`** — the field is already emitted and already
   `None`. Base AC then stays correct whether or not the bonus is understood.
3. **Do not turn non-armour into armour.** Restrict the equipment branch to real armour
   `item_type`s, and express a wondrous/ring/weapon AC bonus as an ActiveEffect on
   `system.attributes.ac.bonus`.
4. **Add a gate.** A worn armour whose `armor.value` is below 10 is almost certainly this
   bug; nothing legitimate sits there.

## Tests to add

- `itemmodifiers` with both `AC: 15` and `AC +2` yields `armor.value == 15` and
  `armor.magicalBonus == 2` (fails against current source — currently yields `2` / `None`).
- `Item Type: Ring, AC +1` does **not** produce an item with `armor.value` set.
- `Item Type: Light Armor, AC: 11` with no bonus still yields `armor.value == 11`.

## Why the gates missed it

`armor.value` is item data; **AC is computed at runtime from equipped items**. Gate A reads
files and never evaluates the actor, so it reported 20 pass either side of the collapse. The
lesson recorded in the pipeline doc applies directly: *a check that only reads the file
cannot see what the system computes.*
