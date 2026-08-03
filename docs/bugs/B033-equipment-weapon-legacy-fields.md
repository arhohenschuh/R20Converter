# B033: Equipment/weapon items carry legacy or wrong 5.x fields (armor.dex=0, `stealth`, `speed`, weapon `armor.value=10`)

- **Status**: Fixed in 1.0.1 (F033)
- **Severity**: Major (armor dex cap wrong) / Minor (the rest is dropped junk)
- **Found**: 2026-08-03 audit
- **Component**: `src/entities/items.py:684-699` (`ItemObject`), `1087-1120` (`ItemEquipment`), `src/entities/actors.py:1845-1870` (`addInventoryItem`)

## Defects

1. **`armor.dex` emitted as `0` for every armor.** `ItemEquipment.__init__`
   defaults `dexterity=0` and the OGL path never sets it, so every converted
   armor stores `armor.dex: 0`. In 5.x (`module/data/item/equipment.mjs:56-60`)
   `dex` is nullable: `null` = unlimited dex, `0` = "max +0 dex" (heavy armor).
   Every converted light/medium armor therefore computes AC without dex the
   moment the actor's AC calc is switched from `flat` to equipped armor.
   Correct emission: `null` unless the armor genuinely caps dex (medium → 2,
   heavy → 0).
2. **`stealth` boolean is legacy.** 5.x expresses stealth disadvantage as the
   `"stealthDisadvantage"` entry of the `properties` set; the `system.stealth`
   boolean only survives via a migration shim
   (`equipment.mjs:245-250`, sets `flags.dnd5e.migratedProperties`) — the exact
   dependence on migrations ADR-008 exists to eliminate. The converter also
   never emits a `properties` array for equipment at all (`mgc`, `ada`, `foc`,
   `stealthDisadvantage` are all expressible).
3. **`speed` block** on equipment is not in `EquipmentData` (vehicle movement
   moved elsewhere); dropped on load — emit nothing.
4. **`ItemObject` junk on weapons/equipment.** `createItemWeapon`/`Equipment`
   splice in `armor: {value: 10}` and an `hp` block. `WeaponData.armor.value`
   is the *weapon's own* AC (siege equipment); every converted weapon claiming
   AC 10 is wrong data (initial is `null`), and `hp` is not in the 5.x weapon
   schema at all.

## Suggested fix

Emit `armor.dex` as `None`/2/0 by armor type; translate `stealth=True` into
`properties: ["stealthDisadvantage"]`; drop the `speed` block and the
`ItemObject` splice entirely (its `getDict` is already marked "Unused" — it just
is not unused).
