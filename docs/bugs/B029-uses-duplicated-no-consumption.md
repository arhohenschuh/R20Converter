# B029: Item `uses` are duplicated onto the activity and no `consumption.targets` is emitted

- **Status**: Fixed in 1.1.0 (F029)
- **Severity**: Major (limited-use features never consume a use)
- **Found**: 2026-08-03 audit
- **Component**: `src/dnd5e.py:448-499` (`applyActivityMetadata`, `_activityBase`), `src/entities/items.py:351-361` (`createStandardData`)

## Defect

For a non-spell item with limited uses ("2/day" feature, charged trinket):

1. `createStandardData` writes the translated `uses` block onto the **item root**
   (correct — `ActivitiesTemplate` declares it there), and
2. `applyActivityMetadata` (`on_item=False` for every non-spell type) **also**
   deep-copies the same block onto the **activity** (`dnd5e.py:477-478`), and
3. `_activityBase` always emits `consumption: {targets: [], spellSlot: True, ...}`
   — an empty target list.

dnd5e's own migration does the opposite. `BaseActivityData.transformUsesData`
(`module/data/activity/base-activity.mjs:535-549`) leaves activity uses **empty**
(except the recharge+charges combination), and `transformConsumptionData`
(`base-activity.mjs:328-337`) wires the activity to the item pool whenever the item
has max uses:

```js
else if ( source.system.uses?.max ) targets.push({
  type: "itemUses", target: "", value: "1", ...
});
```

## Impact

- Activating a limited-use item **never decrements its uses** — there is no
  consumption target, so dnd5e has nothing to spend.
- The activity carries a phantom second uses pool (same max, own `spent`), which
  the sheet displays alongside the item's pool.

Applies equally to innate-cast NPC spells ("3/day each"): the spell root gets the
uses, the cast activity consumes nothing.

## Suggested fix

Stop copying `uses` onto the activity in `applyActivityMetadata` (drop the `uses`
parameter for the non-spell path); when the item has `uses.max`, emit
`consumption.targets = [{"type": "itemUses", "target": "", "value": "1",
"scaling": {"mode": "", "formula": ""}}]` on the activity, mirroring
`transformConsumptionData`. Keep the recharge special case aligned with
`transformUsesData`.
