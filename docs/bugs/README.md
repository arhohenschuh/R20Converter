# Bug annotations

Findings from the 2026-08-03 dnd5e-output and codebase audit, numbered
continuing the **B0xx** sequence from `ROADMAP.md` (B001–B026, all fixed).
These are **open** — documented, not fixed. Each file records the defect, the
evidence in the dnd5e 5.3.3 source (read from the actual system source, per the
ADR-008 discipline), the user-visible impact, and a suggested fix.

Reference material used: dnd5e 5.3.3 source (`module/config.mjs`,
`module/data/**`), a live dnd5e 5.x install (LevelDB packs), and two published
converted modules (*Lost Mine of Phandelver*, *Out of the Abyss*) for
structural comparison. The unit suite is 513-green throughout — every finding
below sits in territory the suite does not assert, which is the B011 lesson
repeating.

## Index

| ID | Severity | Summary |
| --- | --- | --- |
| [B027](B027-class-compendium-keyerror.md) | Critical | `createItemClass` crashes (`KeyError: 'saves'`) when a class matches a compendium entry — F019 removed the keys but not the `del`s. Currently masked by B031. |
| [B028](B028-weight-price-attunement-schema.md) | Major | Numeric `weight`/`price` where 5.x declares `{value, units}` / `{value, denomination}` objects — every physical item loses both. `attunement` numeric vs 5.x string. |
| [B029](B029-uses-duplicated-no-consumption.md) | Major | Item `uses` duplicated onto the activity and no `consumption.targets` emitted — limited-use items never spend a use; dnd5e's own migration wires `itemUses` instead. |
| [B030](B030-npc-spellcasters-zero-slots.md) | Major | NPC casters get zero spell slots: emitted `details.spellLevel: 0` migrates to caster level 0 and defeats dnd5e's `max(cr, 1)` fallback; `spells.spellN.max` is not in the schema and `override` is never set. |
| [B031](B031-system-packs-leveldb-unreadable.md) | Major | Pack loading reads NeDB `.db` files; dnd5e ≥3.0 ships LevelDB directories — on current installs no packs load and all compendium enrichment silently degrades. |
| [B032](B032-token-bars-unknown-attribute.md) | Major | Unlinked token bars point at `attributes.bar1`/`bar2`, which no 5.x actor schema declares — the common unlinked NPC HP bar renders empty and per-token HP overrides are dropped. |
| [B033](B033-equipment-weapon-legacy-fields.md) | Major | Every armor emits `armor.dex: 0` (a dex cap of +0); equipment `stealth`/`speed` are legacy; `ItemObject` stamps `armor.value: 10` + `hp` on every weapon. |
| [B034](B034-xp-parse-and-shadowed-max.md) | Minor | `createDetailXP` wipes slash-format XP to 0 and shadows the `max` builtin (pct computation always TypeErrors, silently). |
| [B035](B035-hlbonus-comparison-noop.md) | Minor | `hlbonus == ""` no-op comparison — spells with `spellhlbonus = 0` get junk `" + 0"` scaling and a scaling mode they shouldn't have. |
| [B036](B036-innate-uses-single-digit.md) | Minor | Innate uses regex `(\d)` — "10/day" becomes 1 use with no recovery period. |
| [B037](B037-toolprof-legacy-traits.md) | Minor | Character tool proficiencies emitted as legacy `traits.toolProf`; 5.x stores a `system.tools` mapping (works only via a migration shim). |
| [B038](B038-shaped-skills-legacy-shape.md) | Minor | Shaped-sheet custom skills still emit the pre-5.x shape B022 removed elsewhere; `passive = mod = …` chained assignment and an inverted bonus sign on top. |
| [B039](B039-recovery-periods-charges.md) | Minor | `RECOVERY_PERIODS` whitelists `"charges"`, which is not a 5.x recovery period (latent — `ItemUses.PER_CHARGES` is never assigned). |
| [B040](B040-backpack-type-and-capacity.md) | Minor | `"backpack"` type triggers dnd5e's source migration (`persistSourceMigration`) and the 1.5.6 capacity shape is dropped (latent — path currently unreachable). |
| [B041](B041-npc-creature-type-not-split.md) | Minor | `details.type.value` stores "humanoid (goblinoid)" whole instead of value + subtype; swarms unhandled. |
| [B042](B042-short-hex-color-expansion.md) | Minor | 3-digit hex colors expand ×16 instead of ×17 (`#fff` → `#f0f0f0`). |

## Cross-cutting observations

- **B027 × B031**: the crash is unreachable until pack loading works again.
  Whoever fixes B031 must fix B027 in the same change or every SRD-classed PC
  conversion will crash.
- **B028/B033/B037/B038** are all the B009 pattern — a template block that was
  ported for the item types the tests looked at and missed elsewhere. A
  schema-diff test that walks *every* emitted `system` dict against the 5.3.3
  `defineSchema` key set (the `test_dnd5e_template.py` approach, generalised)
  would catch the whole class.
- **Numbering**: next free ID is **B043**; fixes should take F0xx numbers and
  move the entry into the `ROADMAP.md` table as B001–B026 did.
