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

**B044–B046 were found on 2026-08-04**, outside that audit, starting from a live
vision failure in a converted world and tracing back to the converter rather than
to the world. **B045 and B046 are fixed in 1.7.0** (F045–F046); **B044 needed a
second pass** — its first fix (F044, 1.7.0) derived PC darkvision from the token's
night-vision radius, which field evidence gathered the same day showed was unsound
before it shipped further; the corrected fix (F047, 1.7.2) matches the race name
against a hand-verified table instead, and does not reopen the compendium-lookup
approach ADR-007 already rejected. B044 and B045 are independent causes of one
symptom — how far a token sees and through what arc — which is why neither fix
restores vision alone. B046 was found by a regression test written for B044, not
by reading the code.

**B047 was found on 2026-08-04 by a user**, not by the suite: the
`conversion-log.txt` feature added in 1.7.1 created the output directory a
statement before `convert()` did, so **1.7.1 and 1.7.2 could not convert
anything at all**. Fixed in 1.7.3 (F048). The suite went 594 -> 644 green across
those releases while the product's one function was broken, because every test
exercised a component and none exercised a conversion.

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
| [B031](B031-system-packs-leveldb-unreadable.md) | Major | Fixed (F031b) | Pack loading read NeDB `.db` files while dnd5e ≥3.0 ships LevelDB directories, so all compendium enrichment was silently disabled. Reported with its real cause in 1.0.1; fully fixed in 1.3.0 once ADR-009 brought in the LevelDB dependency. |
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
| [B044](B044-senses-not-populated-and-legacy-path.md) | Major | Fixed (F044, F047) | Senses now emit the dnd5e 5.3 `senses.ranges.*` mapping instead of the flat pre-5.3 keys (394/394 verified), and NPC parsing is unaffected (215/371). Player-character darkvision is derived from a hand-verified race-name table (F047), not a compendium lookup (ADR-007 already rejected that) and not the token's night-vision radius (F044's first attempt, measured unsound the same day). |
| [B045](B045-zero-sight-angle-blinds-token.md) | Critical | Fixed (F045) | `sightAngle`/`lightAngle` returned **0** for Roll20's "no field-of-vision limit", but Foundry reads `sight.angle: 0` as a **zero-degree cone** (schema default 360). The token was blind whatever its senses said. 394 of 394 prototype tokens affected in the reference world. |
| [B046](B046-passive-perception-and-list-mutation.md) | Minor | Fixed (F046) | NPC `senses.special` kept `passive Perception NN`: the guard compared case-sensitively against Roll20's capitalised text, and the loop called `pop(i)` while enumerating, skipping the following entry. Found by a B044 regression test, not by reading. |
| [B047](B047-conversion-log-creates-output-directory.md) | Critical | Fixed (F048) | The 1.7.1 conversion log created the output directory via `makedirs(exist_ok=True)`, one statement before `convert()`'s bare `makedirs` — so every conversion died with `FileExistsError`. Relaxing that second call was rejected: it is the GUI's only guard against converting over an existing world. The log now buffers until the directory exists. |
| [B048](B048-cdn-host-not-updated-art-lost.md) | High | Fixed | Downloads never tried Roll20's current CDN host, so every `s3.amazonaws.com` asset 403'd and was lost. `hostCandidates` derives the renamed host from the old URL — no lookup needed. Must be fixed together with B049. |
| [B049](B049-zip-miss-not-downloaded.md) | High | Fixed (keep) | An asset absent from the export zip was abandoned without trying the URL already in hand. **Re-diagnosed:** 111 of the 116 misses were B053, not missing assets — this fallback masked that defect by silently downloading files that were on disk. Kept as a safety net, now with a bulk-miss warning. |
| [B050](B050-pc-class-level-always-one.md) | Critical | Fixed | `--no-compendium-overwrite` discarded per-character state on compendium-matched items, so every PC's class level reverted to 1. Silent, and the sheet looks fine. |
| [B051](B051-properties-boolean-map-breaks-migration.md) | High | Not a defect in 1.7.3 | `system.properties` as a boolean map fails item validation. Legacy data in packs built by older converters; current output is correct. |
| [B052](B052-line-separator-breaks-nedb-world.md) | Critical (where it occurs) | Not a converter defect | A raw U+2028 makes a NeDB world unloadable. Traced to a post-conversion repair tool — the converter's `json.dumps` escapes it. Gated by the pipeline suite (G19). |
| [B053](B053-pdf-in-journal-shifts-zip-paths.md) | High | Fixed | Roll20 allows PDFs in the journal tree; `addToFolder` skipped them without advancing its index, so every later sibling was numbered one below the zip. Cost 116 assets on *Dragoncoast Danger* and was misattributed to the exporter. The root cause behind B049. **Blast radius initially understated:** the first sweep scored only journal *folders* and cleared *Storm over Savage Frontier*, whose handout directories were 397/448 correct. |
| [B054](B054-ac-bonus-overwrites-base-armor-value.md) | High | Fixed | Roll20 emits `AC: 15` and `AC +2` as separate `itemmodifiers` entries; `addInventoryItem` parses them into a flat dict, so the bonus **overwrites the base** and a Half Plate +2 converts with `armor.value = 2`. Invisible until the armour is equipped. Also turns rings/cloaks granting +1 AC into `clothing` items that grant nothing. |
| [B055](B055-item-folder-numbering-ignores-siblings.md) | High | Fixed | `Items.addToFolder` advanced its index only for sub-folders — the handout/character branches sat behind `elif is_items_folder`, and there was no `pdf` branch at all. Storm derived `029 - Magic Items` against a real `074`; Wardens `005` against `083`. Third instance of a fallback hiding its own cause: the 1.7.4 manifest lookup resolved the assets by URL, so no shipped world is damaged. |
| [B056](B056-asset-extension-not-renderable.md) | High | Fixed | The stored extension came from the Roll20 URL, not the content. A cache-buster after `&` survived (`….svg&cb=5`), and `.jfif` is absent from Foundry's `IMAGE_FILE_EXTENSIONS`, so the *Lakeside* map converted to the correct path and was never drawn. Every existing check passed — the file existed, was non-empty and resolved; nothing asked whether the client could render it. Re-measured at **139 members across 5 campaigns**, and the 1.7.7 fix reached only `downloadResource`; `copyZipFile`, the path every bundled asset takes, was completed in 1.9.0. |
| [B057](B057-walls-do-not-restrict-movement.md) | High | Fixed | `move` came from Roll20's page-level `lightrestrictmove`, which is `true` on 52 pages, `null` on 616, and **never `false`** — an "off" state indistinguishable from "never set", on a legacy field Jumpgate stopped maintaining. **136,884 of 248,169 wall segments (55%)** converted with `move: 0`: purple in Foundry, and tokens walk through them. Nothing in Gate A or Gate B reads `move`, so 21 conversions shipped this way. |
| [B058](B058-legacy-dl-doors-become-walls.md) | High | Fixed (v1.10.1; v1.10.0 superseded) | Legacy DL doors are wall-layer paths distinguished by colour. The GUI enabled detection while the CLI disabled it, so doors became walls. The first fix then ranked colours by frequency and swept rank 3+ into secret doors; immutable controls proved it could invert blue walls/orange doors and turn `transparent` into secrets. The hash-pinned official baseline is **155 of 314 walled pages** and 3,929 minority segments. v1.10.1 normalizes colours, infers only canonical orange ordinary doors on non-native pages, never infers secrets, reports native-page residue, refuses unknown palettes, and asserts post-cleanup conservation. Existing world repair remains separate. |
| [B059](B059-quadratic-paths-use-control-point-as-vertex.md) | Minor | Open documented limitation | Quadratic Bézier control points are emitted as wall vertices rather than used to flatten the curve, so one `Q` attempts two straight Walls through an off-curve point and source/converter segment units diverge. |
| [B060](B060-scenes-migrate-with-exploration-disabled.md) | High | Fixed (v1.11.1) | Scenes emitted removed `fog.exploration`, which Foundry 14 migrated to `fog.mode: 0` (None); Token Vision was also conditional on legacy lighting flags. Current output defaults every Scene to Token Vision plus Individual exploration. |
| [B061](B061-token-name-display-varies-by-roll20-flags.md) | Minor | Fixed (v1.11.2) | Actor prototype and placed Token names inherited inconsistent Roll20 visibility flags. Both now serialize Foundry's Always for Owner mode (`displayName: 40`). |
| [B062](B062-compendium-overwrite-discards-spell-state.md) | High | Fixed (v1.11.2) | `--no-compendium-overwrite` replaced source spell method, preparation, uses, and consumption with compendium defaults, making innate/at-will/ritual spells demand slots or lose availability. |
| [B063](B063-leveldb-writer-stops-at-one-embedded-level.md) | High | Fixed (v1.12.0) | Module LevelDB serialization stopped after one embedded level and kept Token ActorDelta and Item ActiveEffect documents inline, so Foundry could not resolve their standalone pack relationships. |
| [B064](B064-actor-resource-contracts-incomplete.md) | High | Fixed (v1.13.0) | Module NPCs could ship partially spent or empty spell-slot pools, and no emitter gate rejected spell activities whose item-use or double-consumption dependencies were unsatisfiable. |
| [B065](B065-module-output-not-self-contained.md) | High | Fixed (v1.14.0) | Module exports had no Adventure pack, retained external HTML art and executable compendium targets, and could manufacture broken self UUIDs for source links whose target was absent. |
| [B066](B066-dice-only-weapons-cancel-ability-modifier.md) | Minor | Fixed (v1.14.0) | Dice-only weapon damage was stored as a negative base bonus plus `@mod`; totals matched, but the representation was structurally fragile and failed G30. |
| [B067](B067-strict-reader-rejects-third-party-pack-drift.md) | High | Fixed (v1.14.0) | Applying emitted-pack relationship strictness to third-party compendium inputs made one malformed donor pack disappear from enrichment instead of recovering its unlisted children. |
| [B068](B068-spell-resource-gate-blocks-non-spell-donors.md) | High | Fixed (v1.14.0) | The G29 spell-resource validator ran on every Item and aborted LMoP on Beyond5e's known Torch no-pool defect, even though non-spell donor QA is outside the Actor spell-resource contract. |
| [B069](B069-path-custom-compendium-uses-filesystem-as-package-id.md) | High | Fixed (v1.14.0) | A custom compendium supplied by path used that path as its package ID, so valid executable UUIDs could not match donors loaded from the same module. |
| [B070](B070-zero-byte-zip-asset-is-accepted.md) | High | Fixed (v1.14.0) | Asset copy accepted zero-byte ZIP members as successful local files, preventing CDN fallback and leaving references that resolved to content Foundry could not render. |
| [B071](B071-prose-compendium-targets-remain-external.md) | High | Fixed (v1.14.0) | External Actor/Item UUIDs embedded in prose were only recommended even when their donor existed, so imported content could still depend on an optional module at runtime. |
| [B072](B072-nonordinal-caster-level-is-ignored.md) | High | Fixed (v1.14.0) | Roll20's observed `4-level spellcaster` prose did not match the ordinal-only caster parser, leaving ordinary NPC spells with no initialized module slot capacity. |
| [B073](B073-adventure-journal-hierarchy-not-source-backed.md) | High | Fixed (v1.14.0) | Adventure assembly copied whatever Journal folders happened to be in the pack instead of fail-closed projection from the immutable Roll20 `journalfolder` tree. |
| [B074](B074-cloned-donor-token-name-visibility-drifts.md) | Minor | Fixed (v1.14.0) | Actors cloned to close executable dependencies retained donor prototype Token name visibility instead of the module-wide Always-for-Owner policy. |
| [B075](B075-missing-compendium-link-becomes-invalid-item-uuid.md) | Minor | Fixed (v1.14.0) | An unresolved Roll20 compendium link became `@UUID[Item.<visible name>]`, manufacturing a dangling world Item UUID instead of preserving readable text. |
| [B076](B076-dynamic-layer-circles-are-skipped.md) | High | Fixed (v1.15.0) | Dynamic-layer circles are flattened into deterministic, transformed, closed Walls; immutable ToA verifies 224 paths / 3,584 segments across 27 Scenes. |
| [B077](B077-donor-activity-mismatch-drops-innate-consumer.md) | High | Fixed (v1.15.0) | Mismatched multi-activity donors receive exactly one bounded consumer on a deterministic primary; limited innate spells cannot pass with zero or multiple consumers. |
| [B078](B078-structured-innate-cadence-is-ignored.md) | High | Fixed (v1.15.0) | Structured `data-Spells` and unambiguous trait clauses now drive native cadence; all nine measured ToA rows infer from immutable source. |
| [B079](B079-system-summon-with-empty-texture-is-not-localized.md) | High | Fixed (v1.15.0) | System Actor summons are art-qualified; null-art donors localize once using the invoking Item icon or fail with the exact UUID. |
| [B080](B080-roll20-placeholder-is-stored-as-art.md) | High | Fixed (v1.15.0) | The exact Roll20 placeholder body is rejected across acquisition paths; complete HTML tags are stripped and structural image fields fail closed. |
| [B081](B081-inline-innate-cadence-boundary-is-swallowed.md) | High | Fixed (v1.15.2) | A second cadence marker on the same trait line was swallowed into the first spell list, causing valid explicit spell cadence to fail as contradictory. |
| [B082](B082-unique-slot-consuming-donor-primary-not-selected.md) | High | Fixed (v1.15.2) | A multi-activity donor with one initial slot-consuming cast and one free follow-up was rejected because neither activity had the canonical primary ID. |
| [B083](B083-transform-followup-blocks-limited-innate-primary.md) | High | Fixed (v1.15.2) | Polymorph's save cast and transform follow-up both advertised slot consumption, leaving a utility-shaped source row with no recognized primary. |
| [B084](B084-zero-area-jumpgate-ellipse-aborts-conversion.md) | High | Fixed (v1.15.2) | Jumpgate ellipse bounding-box corners were treated as polygon vertices; all 12 Eberron ellipses failed instead of yielding 128 Walls plus four explicit debris skips. |
| [B085](B085-rolltable-prose-target-is-not-localized.md) | High | Fixed (v1.15.2) | Custom compendium loading discarded declared RollTable packs and the assembler matched only Actor/Item UUIDs, leaving Confusion linked to its build-time donor. |
| [B086](B086-markdown-links-bypass-rich-text-localization.md) | High | Fixed (v1.15.2) | Markdown links embedded in rich-text fields bypassed HTML link resolvers and remained literal in source packs and the Adventure. |
| [B087](B087-relative-html-images-have-no-package-root.md) | High | Fixed (v1.15.2) | Bare HTML image paths were neither localized nor removed, so they resolved against a server data root and broke on every other installation. |
| [B088](B088-module-output-drops-source-macros.md) | High | Fixed (v1.15.2) | Module mode never instantiated or saved Macros and hardcoded an empty Adventure macro collection, dropping all 87 Eberron Setting macros. |
| [B089](B089-primary-adventure-documents-lack-schema-stamps.md) | High | Fixed (v1.15.2) | Folder, JournalEntry, Macro, Scene, and source RollTable primaries lacked `_stats`, leaving 886 Adventure documents without a core schema version. |
| [B090](B090-compendium-type-mismatch-replaces-source-weapon.md) | High | Fixed (v1.15.3) | Explicitly typed source Items now reject incompatible same-name donors; a source NPC weapon retains its attack and damage. |
| [B091](B091-npc-item-names-retain-source-whitespace.md) | Minor | Fixed (v1.15.3) | NPC Item names are trimmed before placeholder selection, lookup, activity-ID derivation, and document creation. |

## Cross-cutting observations

- **B027 × B031**: the crash was unreachable until pack loading worked again.
  Both were addressed in the same change for that reason — F031 alone would have
  turned a silent degradation into a crash for every SRD-classed PC.
- **B028/B033/B037/B038** are all the B009 pattern — a template block that was
  ported for the item types the tests looked at and missed elsewhere. All four
  are now closed, and `tests/test_dnd5e_schema_diff.py` covers both the item and
  actor sides so the next one fails a test rather than waiting for an audit.
- **Numbering**: next free ID is **B092**; fixes take F0xx numbers.
- **B049 × B053**: the clearest case yet of a workaround hiding its own cause. B049's
  download fallback repaired 112 of 116 assets, so a systematic path-derivation bug
  presented as flaky CDN behaviour and survived two days — including a day spent
  suspecting the exporter. A fix that silently restores the expected output removes the
  pressure to explain the anomaly; `noteZipMiss` now makes the fallback announce how often
  it fires.
- **B050 × B054**: both corrupt a character silently and both stay hidden until something
  *recomputes* the sheet. B054 in particular survived three published worlds because the
  affected armour was never equipped — the file-reading gates saw correct-looking item data
  and a correct-looking flat AC override at the same time. **A check that only reads the
  file cannot see what the system computes**; verifying a character means loading the world
  and reading the derived value.
- **B057 × B058**: one wall record, two independent losses, neither visible to any gate.
  Both come from Roll20's engine migration moving where a meaning lives — `move` from a
  page-level legacy flag, and *door-ness* from a stroke-colour convention to a `doors[]`
  object — and in both cases the converter kept reading the old location and emitted a
  plausible default. The walls are present and correctly positioned either way, so every
  structural check passes; the damage only appears when a token tries to move or a player
  tries to open a door. **Geometry being right is not evidence that behaviour is right** —
  scenes need assertions on `move` and `door` against the source, not just on coordinates.

## Candidates resolved

- `system.identified` is emitted on every physical item and was flagged because
  it appears in neither `PhysicalItemTemplate` nor `EquippableItemTemplate`.
  **Not a bug**: it is declared in `IdentifiableTemplate`
  (`identified: new BooleanField({required: true, initial: true})`), which the
  physical item types also mix in. The converter is correct.
