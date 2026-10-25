# B122: PC ammunition converts to a weapon of invalid type `ammo`

- Severity: Moderate
- Status: Open
- Observed release: R20Converter 1.16.2, commit 9c485df; source unchanged in 1.16.3 (39d9eaf)
- Reported: 25 October 2026, Dragoncoast Danger PC relevel (`dcd/relevel-001`), Foundry 14.369,
  dnd5e 6.0.6 Legacy

## Reproduction

Roll20 PCs Medela Marigold Middleton and Neverell Obarskyr (Dragoncoast Danger R20Exporter 1.5.3)
each carry an inventory row *Crossbow bolts* x20 with item type `Ammunition`. The converted actors
contain `type: "weapon"`, `system.type.value: "ammo"`, no activities. `ammo` is not a key of
`CONFIG.DND5E.weaponTypes` (`simpleM, simpleR, martialM, martialR, natural, improv, siege`); in dnd5e
2014 ammunition is `type: "consumable"`, `system.type.value: "ammo"`, with a subtype such as
`crossbowBolt`.

Live effects (`Reports/inspect-ammo-options-001.json`): each PC's *Light Crossbow*
(`ammunition.type = crossbowBolt`) offers **no** ammunition options, so firing never selects or
spends a bolt. Copying the item to another actor makes dnd5e's weapon `_preCreate` add a default
*Attack* activity to the bolts, giving a spurious attack row.

## Cause

`src/entities/actors.py`: inventory rows of type `Ammunition` take the weapon path
(`item_type in ["Melee Weapon", "Ranged Weapon", "Ammunition"]`) and set
`weapon.type = ItemWeapon.AMMUNITION`, where `ItemWeapon.AMMUNITION = "ammo"`
(`src/entities/items.py`).

## Expected Behavior

Source ammunition rows convert to consumables of type `ammo` with the matching dnd5e ammunition
subtype (`arrow`, `crossbowBolt`, `slingBullet`, `blowgunNeedle`, ...), keeping quantity, weight,
price and description, so ranged weapons with the Ammunition property can select and consume them.
An unrecognised ammunition name keeps the consumable `ammo` type without a subtype and logs a
warning.

## Regression Requirements

- *Crossbow bolts* x20 (`Ammunition`) converts to a consumable `ammo`/`crossbowBolt` x20 and appears
  in a Light Crossbow's ammunition options.
- A different character/module with *Arrows* x20 converts to `ammo`/`arrow`.
- Control: a Melee Weapon / Ranged Weapon row is unchanged.
