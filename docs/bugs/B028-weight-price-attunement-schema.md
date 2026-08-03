# B028: Physical items emit numeric `weight`, `price` and `attunement` — 5.x declares objects/strings

- **Status**: Fixed in 1.0.1 (F028)
- **Severity**: Major (silent data loss on every physical item)
- **Found**: 2026-08-03 audit
- **Component**: `src/entities/items.py:956-965` (`ItemInventoryAttributes.getDict`)

## Defect

Every weapon, equipment, consumable, tool, loot and handout-derived item emits:

```python
{"rarity": ..., "quantity": ..., "weight": 1, "price": 0, "attunement": 0,
 "equipped": ..., "identified": ...}
```

dnd5e 5.3.3 `PhysicalItemTemplate` (`module/data/item/templates/physical-item.mjs:26-41`)
declares:

- `weight: SchemaField({ value: NumberField, units: StringField })`
- `price: SchemaField({ value: NumberField, denomination: StringField })`

A bare number fails `SchemaField` validation and Foundry repairs the field to its
initial on load, so **every converted item loses its weight and price** — exactly
the "quiet rather than loud" failure mode described in the dnd5e.py activated-effect
comment. The suite is green because it asserts the emitter's own output shape.

`attunement` is a `StringField` in 5.x (`templates/equippable-item.mjs:19`, values
`""`/`"required"`/`"optional"`); the numeric `0` is cast to the junk string `"0"`.
Today the converter only ever emits `0`, so the damage is cosmetic — but the field
is one legacy write away from breaking real attunement data.

## Suggested fix

Add `dnd5e.weightData(value, units="lb")` and `dnd5e.priceData(value,
denomination="gp")` builders mirroring `physical-item.mjs`, map legacy numeric
attunement (`0/1/2` → `""`/`"required"`/`"required"`), and cover the shapes in
`test_dnd5e_template.py` the same way B009 was covered — asserting the fields the
5.3.3 schema declares, not the ones the emitter produces.
