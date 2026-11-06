# B125: Unmatched items inherit the actor portrait as their icon

- Severity: Moderate
- Status: Open
- Observed release: R20Converter 1.16.4, commit 404ef6a; the fallback predates the B0xx register
- Reported: 6 November 2026, Dragoncoast Danger live world (`dragoncoast-danger`, Pi), Foundry 14.369,
  dnd5e 6.0.6 Legacy, Beyond5e 2014 compendium and assets installed

## Reproduction

Convert any OGL actor with an item, feature, or spell that has no exact-name match in the
installed system packs. The converted item's `img` is the actor's avatar, or its token image when
there is no avatar. The sheet then shows the character portrait on every unmatched row instead of
an item icon.

Dragoncoast Danger on the Pi, before the downstream repair, counted by the owning actor's `img` or
prototype token texture:

| Population | Items with the portrait icon | Typical names |
| --- | --- | --- |
| PCs and companions (8 actors) | 45 | *Quarterstaff (One-Handed)*, *Dagger (melee)*, *Warhammer (Two-Handed)*, *Belt Pouch*, *Hempen rope*, *Cunning Action*, *Sneak Attack*, *Thieves' Tools* |
| PC backup copies (6 actors) | 38 | the same items on the `(Copy)` actors |
| NPCs and monsters (232 actors) | 1,051 | *Multiattack* (117), *Dagger* (48), *Spellcasting* (41), *Innate Spellcasting* (38), *Sunlight Sensitivity* (33), *Fey Ancestry* (25) |

Of the 1,051 NPC items, 836 have an exact-name item or monster feature with its own icon in the
Beyond5e compendium, and 13 more match after removing a printed suffix or prefix. Only 202
have no equivalent. In the 2014 Legacy system packs alone, many of these names do not exist,
especially monster features.

## Cause

`src/entities/actors.py` falls back to `self._avatar_filename` whenever no compendium entry is
found:

| Builder | Fallback |
| --- | --- |
| `createItemInventory` | `compendium_item.entity["img"] if compendium_item else self._avatar_filename` |
| `createItemFeat` | same; for NPCs `compendium_item` is always `None` (B100), so every NPC trait, action, bonus action, reaction, and legendary action receives the portrait |
| `createItemSpell` | same |
| `createItemClass` | same |
| `createItemSubclass`, `createItemOrigin` | always `self._avatar_filename` |

`findCompendiumItem` (`src/entities/base.py`) is an exact, case-insensitive name lookup in the
system `items`, `spells`, `classes`, and `classfeatures` packs. Roll20 attack variants
(`Quarterstaff (One-Handed)`, `Dagger (ranged)`), Roll20 gear names (`Belt Pouch`,
`Hempen rope`), and all monster features miss.

An item icon has a different meaning from the actor portrait, so the portrait is never a valid
fallback. Handout-to-item conversion (`src/entities/items.py`, handout avatar) is unaffected: it
uses the handout's own image for the item.

## Expected Behavior

- Never assign the actor avatar or token image to an owned item.
- When a compendium entry exists, copy only its icon. For NPC features, B100 still applies: no
  name-only content or activity replacement. A lookup used only for the icon may use monster
  features and normalized names: strip a trailing parenthetical (`(One-Handed)`, `(Recharge 5–6)`,
  `(1/Day)`), a leading `+N`, a `Variant:` prefix, and a trailing period, and normalize the Roll20
  dash mojibake.
- Otherwise use the dnd5e default icon for the document type (leave `img` unset or use the
  system's per-type default), never a module- or name-specific table.

## Regression Requirements

- PC with *Quarterstaff (One-Handed)*, *Belt Pouch*, and an unmatched homebrew trait: no item
  `img` equals the actor `img` or token texture. The quarterstaff gets the compendium icon when one
  exists; the other items get the type default.
- NPC with *Multiattack*, *Sunlight Sensitivity*, and *Shadow Slip (Recharge 5–6)*: no portrait
  icons. The feature content stays the converted source prose, as B100 requires.
- Actor without an avatar but with a token image: the token image is not used either.
- Control: matched items keep the compendium icon; handout items keep the handout image.
- Use renamed actors and features; the rule must not key on module or actor identity.

## Already Converted Outputs

Every module or world converted with R20Converter up to and including 1.16.4 is expected to
contain this defect and must be checked. "Fixed" for B125 will not repair existing outputs.
Confirmed conversions in this register include Out of the Abyss (B11x Pipeline-11), The Wild
Beyond the Witchlight (`witchlight/v120`), and the Dragoncoast Danger world. Also check every
other publication under `Foundry_Pipeline_Publish` that came from a Roll20 conversion.

Check each output in Foundry by counting owned items whose image is the owner's image, token
texture, or empty:

```js
const hits = [];
for (const a of game.actors) {
  const own = new Set([a.img, a.prototypeToken?.texture?.src]);
  for (const i of a.items) if (!i.img || own.has(i.img)) hits.push(`${a.name}: ${i.name}`);
}
console.log(hits.length, hits);
```

Also run this on module actor packs (`pack.getDocuments()`) and on unlinked scene tokens whose
delta holds item copies.

## Downstream Disposition

Dragoncoast Danger (Pi, live world) was repaired after conversion on 5–6 November 2026. All 1,134
items were reassigned to Beyond5e 2014 icons: exact Beyond5e item or monster-feature names first,
then normalized names, then themed icons from the same asset set. Backups and the assignment plan
are in `D:/Foundry_User/User/_qa-backups/` (`pi-pc-item-icons-before-2026-11-05.txt`,
`pi-pc-copy-item-icons-before-2026-11-05.txt`, `pi-npc-item-icons-before-2026-11-06.txt`,
`pi-npc-item-icons-plan-2026-11-06.json`). This repair belongs to that world's post-conversion
history and is not a converter fix.
