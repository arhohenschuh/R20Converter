# B027: `createItemClass` crashes with KeyError when a class matches a compendium entry

- **Status**: Open
- **Severity**: Critical (crash)
- **Found**: 2026-08-03 audit
- **Component**: `src/entities/actors.py:2515-2517`

## Defect

```python
if compendium_item and compendium_item.entity["type"] != "loot":
    del item.entity["system"]["saves"]
    del item.entity["system"]["skills"]
    del item.entity["system"]["spellcasting"]
```

F019 (B019) removed `saves` and `skills` from `ItemClass.getDict()` — they are not
in the 5.x `ClassData` schema — but these `del` statements in `actors.py` were not
updated. The class item's `system` dict now contains only `description`, `source`,
`levels`, `identifier`, `hd`, `primaryAbility`, `properties`, `spellcasting`, so the
first `del` raises `KeyError: 'saves'` and the whole conversion aborts.

Verified empirically: building the dict via `Item.createStandardData` +
`ItemClass("Fighter", 5).getDict()` and applying the three `del`s raises
`KeyError: 'saves'` and `KeyError: 'skills'`; only `spellcasting` exists.

## Trigger

Any PC whose class name matches an entry in a loaded `Classes` compendium pack
(`findCompendiumItem("Classes", name)` non-None). Currently masked by **B031**:
against a modern dnd5e install no packs load at all, so the lookup always misses.
Fixing B031 without fixing this turns every "Fighter"/"Wizard" PC into a crash.

## Why the suite missed it

`tests/test_dnd5e_origin.py` exercises `ItemClass`/`createItemClass` without a
compendium hit; the branch is only reachable with system packs loaded.

## Suggested fix

Delete the two dead `del` statements and keep only `spellcasting` (or guard all
three with `dict.pop(key, None)`), plus a regression test that runs the
compendium-hit branch.
