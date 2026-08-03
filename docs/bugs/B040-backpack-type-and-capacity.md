# B040: "backpack" item type triggers dnd5e's source migration; capacity uses the 1.5.6 shape

- **Status**: Fixed in 1.1.0 (F040)
- **Severity**: Minor (latent — `createItemBackpack` is currently unreachable from conversion)
- **Found**: 2026-08-03 audit
- **Component**: `src/entities/items.py:292-293`, `531-539`, `1140-1168` (`ItemBackpack`)

## Defect

`createItemBackpack` emits `type: "backpack"` with
`capacity: {type, value, weightless}`.

1. **The type itself is a migration trigger.** dnd5e renamed backpack →
   container in 3.0; `Item5e._initializeSource`
   (`module/documents/item.mjs:94-101`) rewrites the type at load **and flags
   `flags.dnd5e.persistSourceMigration: true`** — the document is queued for a
   rewrite, which is exactly the outcome ADR-008's R4 gate measures to be zero
   ("documents rewritten by the migration: 0"). The gate passed only because the
   acceptance export contained no backpack items.
2. **The capacity shape is 1.5.6.** `ContainerData`
   (`module/data/item/container.mjs:47-62`) declares
   `capacity: {count, volume: {value, units}, weight: {value, units}}`; the
   legacy `{type, value, weightless}` is dropped, so a container converted this
   way holds nothing of its recorded capacity. (`currency` is fine —
   `CurrencyTemplate` is mixed into `ContainerData`.)
3. `quantity` on a container is clamped `min:1, max:1` in 5.x; the generic
   attributes' quantity can exceed it.

Currently latent: `Items.createItemInventory` is never called with
`inventory_type="backpack"` (Roll20 items route to equipment/weapon/loot), so no
converted campaign hits this today. It is one "treat 'Bag of Holding' as a
container" feature away from firing.

## Suggested fix

Emit `type: "container"`; translate legacy capacity: `type=="items"` →
`capacity.count`, `type=="weight"` → `capacity.weight.value` (+ `weightless` →
`properties: ["weightlessContents"]`). Keep B028's weight/price fix in mind —
containers are physical items too.
