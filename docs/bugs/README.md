# Bug annotations

Findings from the 2026-08-03 dnd5e-output and codebase audit, numbered
continuing the **B0xx** sequence from `ROADMAP.md` (B001–B026, all fixed).
Each file records the defect, the evidence in the dnd5e 5.3.3 source (read from
the actual system source, per the ADR-008 discipline), the user-visible impact,
and a suggested fix.

**B027–B035 were fixed in 1.0.1, B037–B038 in 1.0.2, and B029, B030, B036 and
B039–B042 in 1.1.0** (F027–F042 in `ROADMAP.md`). **B031 is only partially
fixed** — see its entry — and **B043 is an open documented limitation.** Every
bug found in the 2026-08-03 audit is now either fixed or explained.

Reference material used: dnd5e 5.3.3 source (`module/config.mjs`,
`module/data/**`), a live dnd5e 5.x install (LevelDB packs), and two published
converted modules (*Lost Mine of Phandelver*, *Out of the Abyss*) for
structural comparison. The unit suite was 513-green throughout the audit —
every finding sat in territory the suite did not assert, which is the B011
lesson repeating. `tests/test_dnd5e_schema_diff.py` now closes that gap
mechanically for the physical-item class of defect.

## Index

| ID | Severity | Status | Summary |
| --- | --- | --- | --- |
| [B027](B027-class-compendium-keyerror.md) | Critical | Fixed (F027) | `createItemClass` crashes (`KeyError: 'saves'`) when a class matches a compendium entry — F019 removed the keys but not the `del`s. Currently masked by B031. |
| [B028](B028-weight-price-attunement-schema.md) | Major | Fixed (F028) | Numeric `weight`/`price` where 5.x declares `{value, units}` / `{value, denomination}` objects — every physical item loses both. `attunement` numeric vs 5.x string. |
| [B029](B029-uses-duplicated-no-consumption.md) | Major | Fixed (F029) | Item `uses` duplicated onto the activity and no `consumption.targets` emitted — limited-use items never spend a use; dnd5e's own migration wires `itemUses` instead. |
| [B030](B030-npc-spellcasters-zero-slots.md) | Major | Fixed (F030) | NPC casters get zero spell slots: `spells.spellN.max` is not in the schema, `override` was never set, and `details.spellLevel: 0` is read as caster level 0. |
| [B031](B031-system-packs-leveldb-unreadable.md) | Major | Partial (F031) | Pack loading reads NeDB `.db` files; dnd5e ≥3.0 ships LevelDB directories — on current installs no packs load and all compendium enrichment silently degrades. Now reported rather than silent; reading them is still unsupported. |
| [B032](B032-token-bars-unknown-attribute.md) | Major | Fixed (F032) | Unlinked token bars point at `attributes.bar1`/`bar2`, which no 5.x actor schema declares — the common unlinked NPC HP bar renders empty and per-token HP overrides are dropped. |
| [B033](B033-equipment-weapon-legacy-fields.md) | Major | Fixed (F033) | Every armor emits `armor.dex: 0` (a dex cap of +0); equipment `stealth`/`speed` are legacy; `ItemObject` stamps `armor.value: 10` + `hp` on every weapon. |
| [B034](B034-xp-parse-and-shadowed-max.md) | Minor | Fixed (F034) | `createDetailXP` wipes slash-format XP to 0 and shadows the `max` builtin (pct computation always TypeErrors, silently). |
| [B035](B035-hlbonus-comparison-noop.md) | Minor | Fixed (F035) | `hlbonus == ""` no-op comparison — spells with `spellhlbonus = 0` get junk `" + 0"` scaling and a scaling mode they shouldn't have. |
| [B036](B036-innate-uses-single-digit.md) | Minor | Fixed (F036) | Innate uses regex `(\d)` — "10/day" becomes 1 use with no recovery period. |
| [B037](B037-toolprof-legacy-traits.md) | Minor | Fixed (F037) | Character tool proficiencies emitted as legacy `traits.toolProf`; 5.x stores a `system.tools` mapping (works only via a migration shim). |
| [B038](B038-shaped-skills-legacy-shape.md) | Minor | Fixed (F038) | Shaped-sheet custom skills still emit the pre-5.x shape B022 removed elsewhere; `passive = mod = …` chained assignment and an inverted bonus sign on top. |
| [B039](B039-recovery-periods-charges.md) | Minor | Fixed (F039) | `RECOVERY_PERIODS` whitelists `"charges"`, which is not a 5.x recovery period (latent — `ItemUses.PER_CHARGES` is never assigned). |
| [B040](B040-backpack-type-and-capacity.md) | Minor | Fixed (F040) | `"backpack"` type triggers dnd5e's source migration (`persistSourceMigration`) and the 1.5.6 capacity shape is dropped (latent — path currently unreachable). |
| [B041](B041-npc-creature-type-not-split.md) | Minor | Fixed (F041) | `details.type.value` stores "humanoid (goblinoid)" whole instead of value + subtype; swarms unhandled. |
| [B042](B042-short-hex-color-expansion.md) | Minor | Fixed (F042) | 3-digit hex colors expand ×16 instead of ×17 (`#fff` → `#f0f0f0`). |
| [B043](B043-foundry-14-unverified.md) | Info | Partial | `compatibility.verified` is now 14, matching the reference module and backed by a document-level comparison against it. `coreVersion` stays 13 deliberately — claiming 14 would make Foundry skip the NeDB→LevelDB migration the output depends on. Writing LevelDB packs directly is still open. |

## Cross-cutting observations

- **B027 × B031**: the crash was unreachable until pack loading worked again.
  Both were addressed in the same change for that reason — F031 alone would have
  turned a silent degradation into a crash for every SRD-classed PC.
- **B028/B033/B037/B038** are all the B009 pattern — a template block that was
  ported for the item types the tests looked at and missed elsewhere. All four
  are now closed, and `tests/test_dnd5e_schema_diff.py` covers both the item and
  actor sides so the next one fails a test rather than waiting for an audit.
- **Numbering**: next free ID is **B044**; fixes take F0xx numbers.

## Candidates resolved

- `system.identified` is emitted on every physical item and was flagged because
  it appears in neither `PhysicalItemTemplate` nor `EquippableItemTemplate`.
  **Not a bug**: it is declared in `IdentifiableTemplate`
  (`identified: new BooleanField({required: true, initial: true})`), which the
  physical item types also mix in. The converter is correct.
