# B050: `--no-compendium-overwrite` discards per-character state on compendium-matched items

- **Status**: **Fixed** — `Item.CHARACTER_STATE_KEYS` + `Item.createItemFromCompendium` in `src/entities/items.py`. Tests: `tests/test_asset_and_compendium_fixes.py`. Worlds shipped before the fix were repaired by hand.
- **Severity**: **Critical** (silent, affects every PC in every conversion, and the sheet looks fine)
- **Found**: 2026-08-05, rebuilding *Wardens of the North Season 3*; confirmed on *Dragoncoast Danger*
- **Component**: `src/entities/items.py`, `Item.createItemFromCompendium`

> **Diagnosis corrected 2026-08-05.** This was first written up as "the converter misreads the
> Roll20 sheet". That is wrong — `actors.py` reads `base_level` and honours `multiclassN_flag`
> correctly. The level is read right and then thrown away. See *Cause*.

## Symptom

Every converted PC has a class Item with `system.levels = 1`, regardless of the character's
real level.

```
Torden Lynn              Roll20: Tempest Domain Cleric 10   ->  Foundry: Cleric 1
Tharok Zephyrblaze       Roll20: Eldritch Knight Fighter 10 ->  Foundry: Fighter 1
Sylvaris R. Lockmere     Roll20: Rogue 7 / Warlock 3        ->  Foundry: Rogue 1, Warlock 1
```

dnd5e derives almost everything from that number, so the whole character is wrong:

| Derived value | Should be (Cleric 10) | Actually |
|---|---|---|
| character level | 10 | **1** |
| proficiency bonus | +4 | **+2** |
| spell slots | 4/3/3/3/2 | **2 first-level** |
| hit dice | 10d8 | **1d8** |

## Why it is easy to miss

**Hit points are unaffected**, because the converter writes `hp.max` as an explicit
override. The sheet therefore shows the correct 92 HP next to a level-1 class, and nothing
looks broken at a glance.

Two further traps hid it during review:

1. A level-1 and a level-4 character **both** have proficiency +2. A Dragoncoast check that
   asserted proficiency passed cleanly while every PC was silently level 1.
2. Spell slots end up internally inconsistent rather than empty — Darthoridan showed
   `L1: 4/2`, four *current* slots against a *maximum* of two, because the current value came
   from Roll20 and the maximum was derived from level 1.

Assert on **`system.details.level`**, never on proficiency alone.

## Cause

`actors.py` builds the class item with the correct level — it reads `base_level`, skips
multiclass slots whose `multiclassN_flag` is `0`, and passes the level down:

```python
base_level = self.getAttribute("base_level", "1")[0]
owned = self.createItemClass(items, pc_class, base_level, subclass)
```

The loss happens one level down. When the class name matches a compendium document,
`createItemClass` rebuilds the item from the compendium and passes the correct system block
as `custom_data`:

```python
item = self._converter.items.createItemClass(None, name, name, level, **kwargs)   # levels = 10
if compendium_item and compendium_item.entity["type"] != "loot":
    item = self._converter.items.createItemFromCompendium(None, compendium_item, item.entity["system"])
```

and `createItemFromCompendium` applies that block **only when `no_compendium_overwrite` is off**:

```python
if custom_data and item.getArgument("no_compendium_overwrite", False) is False:
    item.entity["system"].update(custom_data)          # <-- skipped
```

So under `--no-compendium-overwrite` the compendium's generic class document wins whole, and
its `system.levels` is `1`.

### This is not only about levels

The flag exists to stop the converter's guesses from overwriting good compendium template
data — descriptions, advancements, prerequisites. But `update()` is all-or-nothing, so it
also discards everything that is **per-character state and cannot come from a template**:

| Type | Field lost | Observed |
|---|---|---|
| `class` | `system.levels` | every PC level 1 |
| `weapon` | `system.proficient` | 33 weapons unproficient on Wardens |
| `equipment` | `system.equipped`, `system.quantity` | same mechanism |
| `spell` | `system.preparation` | same mechanism |

The weapon-proficiency repair that Wardens needed was this same bug, not a separate one.

### Why it did not show up everywhere

*Storm over Savage Frontier* is clean: its five PCs converted at levels 12/12/12/6/12,
including Edek's Ranger 5 / Rogue 7 multiclass. Its class items carry **no advancement
array**, i.e. they never matched a compendium document and so took the `else` branch, which
keeps the locally built item and its correct level. Wardens' class items carry 16–29
advancements each — they came from the compendium, and lost their levels on the way.

A conversion is therefore affected only when **both** hold: `--no-compendium-overwrite` is
set, *and* the class name matches the custom compendium. Both are true under the pipeline's
current default settings.

## Suggested fix (not implemented)

Keep the flag's purpose — the compendium still wins on template data — but never let it
discard fields that describe *this* character. Re-apply those after the copy:

```python
# Per-character state can never come from a compendium template, so it survives
# --no-compendium-overwrite. Template fields (description, advancement) do not.
CHARACTER_STATE = {
    "class":     ("levels", "hitDiceUsed"),
    "subclass":  (),
    "weapon":    ("proficient", "equipped", "quantity", "attuned"),
    "equipment": ("proficient", "equipped", "quantity", "attuned"),
    "consumable":("quantity", "uses"),
    "spell":     ("preparation",),
}

if custom_data:
    if item.getArgument("no_compendium_overwrite", False) is False:
        item.entity["system"].update(custom_data)
    else:
        for key in CHARACTER_STATE.get(item.entity["type"], ()):
            if key in custom_data:
                item.entity["system"][key] = custom_data[key]
```

Then assert the result: the class levels must sum to `attrs["level"]`. A mismatch means the
sheet was read wrongly and should be reported rather than written silently.

Worth adding at the same time: stop writing `hp.max` as an override when the class levels
are known, or at least log it — the override is what makes this defect invisible.

## Repair for already-converted worlds

`Foundry_Pipeline_Build\_tools\o8-fix-pc-class-levels.mjs` reads the Roll20
sheet and rewrites each class Item's `system.levels`, handling multiclass via the flags.
Applied to Wardens (9 changes) and Dragoncoast (5).
