# Changelog

## Unreleased

**Targeting Foundry VTT v13.** See `docs/adr/` for the decision records behind
these changes.

### dnd5e 5.x (ADR-008) — in progress

The Foundry **core** schema port (ADR-002) is complete, but every item was still
emitted in dnd5e ~1.5.6 shapes. Unlike Foundry's v9 migrations, dnd5e's migrations
still exist — which is worse than their absence, because they run, report success,
and corrupt:

- The dnd5e migration **never gives weapons an attack**. dnd5e builds the default
  attack in `WeaponData#_preCreate`, which fires on document *creation*; a
  migration is an *update*. Measured across two converted modules: 479/479 and
  742/742 spells migrated with working activities, **393/393 and 524/524 weapons
  migrated with zero** — every weapon unrollable.
- The migration can **silently destroy damage**. It consumes the legacy
  `damage.parts` array and stamps `_stats.systemVersion`, but for a subset of
  documents writes an empty `damage.base` back. A compatibility shim rebuilds the
  base in memory, so the live document reads correctly while the stored one holds
  nothing. Measured: 390 weapons with dice live, 293 stored.

**0.15.0 — foundation (no output change yet).**
- New `src/dnd5e.py`: the single source of truth for dnd5e version numbers and
  data shapes, mirroring `foundry.py`. Constants read out of the dnd5e 5.3.3
  source rather than inferred.
- `DamageData` builder (`damage.base`/`versatile` objects), damage-formula parser
  that survives the degenerate real-world cases (`1d0` nets, flat `1` torches,
  `1d1`), and damage-type normalisation for the dirty values Roll20 emits
  (`"bludgeoning "`, `"spell"`, `"bludgeoning or slashing"`).
- Activity builders — attack, save, damage, heal, utility — with deterministic
  16-character ids so repeat conversions are byte-identical.
- Ability-modifier extraction. Roll20 bakes the modifier into the damage
  (`"Bite 1d10+2"`) while dnd5e always appends `@mod`; the extractor moves it into
  the activity's ability under the invariant that the **printed damage total is
  unchanged**. Ties resolve in a fixed ability order; an unmatched bonus sets
  `attack.flat` rather than subtracting a wrong value.
- `attack.ability = "none"` now raises. It reads back as `null`, but writing it
  fails validation and the activity is *silently* not created.
- `baseItem` resolution from an explicit table (`"Longsword (Melee; Two-Handed)"`
  → `longsword`), returning `""` rather than guessing.
- `_stats` builder — the converter previously emitted none at all.
- 112 new tests, including a damage-invariant table with a non-vacuity guard.
  Suite: 137 → 249.

Fixed during 0.15.0 (see `ROADMAP.md`):
- **B001/F001** — `extractAbilityModifier()` dropped the flat addend on a symbolic
  formula: `"1d8 + @abilities.str.mod + 1"` returned `bonus=0`, so the printed
  total fell by 1. The invariant test had ratified it by discarding the same
  bonus from its expected value.
- **B002/F002** — `attackActivity()` rejected only `ability="none"`, so `"STR"`
  and other invalid keys still produced activities dnd5e validates away.

#### 0.16.0 — the switch

Every dnd5e item shape moves to 5.x **at once**. Sliced any finer the converter
would emit documents neither old enough for dnd5e's migrator nor complete enough
for 5.x: removing `damage.parts` before `activities` exist leaves damage with
nowhere rollable to live. Version stamps move in the same commit as the data,
because claiming 1.5.6 while emitting 5.x invites a migration over documents with
nothing left to convert, and claiming 5.3.3 while emitting legacy fields strands
them.

- `system.type = {value, baseItem}` replaces `weaponType` / `armorType` /
  `consumableType` / `toolType` and the sibling `baseItem`.
- `system.damage.base` / `.versatile` as `DamageData`; `damage.parts` deleted.
- `properties` as an array; the boolean map deleted.
- `system.activities` on every rollable item, so no document depends on the
  migration that never builds them.
- The whole shared activated-effect template: `activation.cost` → `activation.value`,
  the flat `target` → `{template, affects}`, `uses {value, max, per}` →
  `{spent, max, recovery[]}`, `range.long` dropped. Every enum is validated against
  a whitelist read from `config.mjs` — an unrecognised value resolves to the sane
  default instead of silently resetting the field on load.
- Spells: `components` → the shared `properties` set, `preparation` →
  `method` + numeric `prepared`, `scaling` → per-damage-part activity scaling,
  `consume` removed. None of those four keys exists in 5.3.3 `SpellData`.
- **`activation` / `range` / `duration` / `target` are written onto the activity**
  for weapons, features, equipment and consumables. Only `SpellData` declares them
  at the document root; on every other type Foundry drops them and the activity
  keeps its defaults, so a reaction became an action and a 120 ft attack read
  "self". Weapons additionally get their own numeric `range` with `reach`/`long`.
- `_stats` on every item and actor, including handout- and compendium-derived ones.
- Version stamps: `SYSTEM_VERSION`, `dnd5e.systemMigrationVersion`,
  `_stats.systemVersion` and the manifest's `relationships.systems` all read 5.3.3,
  with a `minimum` of 5.0.0.
- Suite: 249 → 429.

Verified by converting a real 65 MB Roll20 export and reading back the emitted
NeDB files — 357 items, 30 actors: **0 legacy fields**, `_stats.systemVersion`
on 357/357 items and 30/30 actors, **0** activated items without an activity
(was 140), 96/96 weapons with dice in `damage.base`, 0 activity id/key mismatches.

Fixed during 0.16.0 (see `ROADMAP.md`):
- **B003/F003** — consumables were routed to `createItemWeapon()`.
- **B004/F004** — `actors.py` read the legacy `weaponType` from compendium items.
- **B006/F006** — spells emitted four fields absent from 5.3.3 `SpellData`, so every
  spell silently lost its components, prepared state and upcast scaling.
- **B007/F007** — an item with an activation but nothing rollable got no activity,
  and therefore no button on the sheet: 26 spells and 114 features.
- **B008/F008** — handout-derived items shipped with no `_stats`.
- **B009/F009** — the activated-effect template was 1.5.6-shaped on every item type.
- **B010/F010** — the heal activity was built without its healing formula, so every
  healing spell healed nothing.
- **B011/F011** — the unit suite was 307-green across all of the above, because it
  only ever asserted the half of the schema the emitter already handled.
- **B012/F012** — `special` and `crew` were dropped from the activation whitelist.
- **B013/F013** — activity metadata (above).
- **B014/F014** — weapons got the shared range shape, losing `reach` and `long` and
  putting a formula string into a `NumberField`.
- **B015/F015** — cantrip save damage was written as `half` on a success; dnd5e sets
  `none`, but only when the key is absent, and the converter always writes one.
- **B016/F016** — compendium-derived items kept their pack's `_stats`.
- **B017/F017** — a recharge overwrote the charge count instead of merging with it.
- **B018/F018** — save activities emitted `save.dc.value` and `damage.critical`,
  neither of which is in the 5.3.3 schema.

#### 0.17.0 — the documents around the items

None of these carries damage, which is why R2 left them alone and why a suite
that only exercises the interesting path never looked at them.

- **Class documents** now emit `hd = {additional, denomination, spent}`,
  `primaryAbility` and `properties`. 5.x replaced `hitDice` / `hitDiceUsed` with
  `hd`, so every converted class arrived at the `d6` default whatever its real
  hit die was — a Barbarian included. `primaryAbility` comes from an explicit PHB
  table, not from the spellcasting ability: a Fighter has a primary ability and
  no spellcasting, and a Paladin's are STR *and* CHA.
- **Actor abilities** emit the 5.x shape. `save` was a number where dnd5e
  declares a `RollConfigField` object, and `mod` / `min` were carried despite
  being derived. The converter still needs those values while translating attacks
  and DCs, so they moved to `_ability_derived` instead of riding in the document.
- **Actor skills** emit formula-string bonuses and the `roll` block.
- **`source`** is a `SourceField` object. As a bare string it was dropped on load,
  which silently removed the attribution from every item and NPC the converter has
  ever produced.

Fixed during 0.17.0 (see `ROADMAP.md`): **B019/F019**, **B020/F020**,
**B021/F021**, **B022/F022**. Suite: 429 → 455.

### Foundry v13 (ADR-002, ADR-003)
- Emit `world.json` and `module.json` in the Foundry v13 manifest schema: `id`
  instead of `name`, the now-required `type`, a `compatibility` object instead of
  `minimumCoreVersion`/`compatibleCoreVersion`, `relationships` instead of
  `dependencies`, and `authors` instead of `author`.
- Compendium packs now declare `type` (the removed `entity` key is gone),
  carry an `ownership` block, and use extension-less LevelDB-style paths.
- Collect every Foundry version and compatibility constant in `src/foundry.py`,
  replacing literals that had drifted out of sync across three files.
### Document schema (ADR-002, ADR-005)
Foundry deleted every automatic v9 → v10 document migration in 12.316, so the
converter now emits the modern field names itself:
- `permission` → `ownership` on every document (the 0–3 levels are unchanged).
- Actors and items store their system data under `system` instead of `data`,
  including the override block carried on a scene token.
- The actor prototype token moved from `token` to `prototypeToken`.
- Folders reference their parent through `folder` instead of `parent`.
- Chat messages carry a `rolls` array instead of a single `roll` string.
- Rollable table results use the v13 shape: string `type` values, a single
  `documentUuid` in place of `collection`/`resultId`, and `name`/`description`
  in place of `text`.
- Journal entries are written as a `pages` array instead of the removed
  `content`/`img` fields. A handout becomes a text page and/or an image page,
  and pages inherit their permissions from the entry.
- Document links embedded in handout text use the `@UUID[…]` enricher rather
  than the deprecated per-type `@Actor[…]` / `@Compendium[…]` forms.
- Compendium entries read from a source pack are up-converted to `system` on
  load, so packs authored for older Foundry versions still work.
- Scenes carry `background` and `grid` objects instead of the flat `img`,
  `shiftX`/`shiftY` and `grid*` fields, plus the current `fog` and `environment`
  groupings.
- Tokens use `texture`, `sight` and `delta` in place of `img`/`tint`/`scale`/
  `mirrorX`/`mirrorY`, `vision`/`dimSight`/`brightSight`/`sightAngle` and
  `actorData`.
- Tiles use `texture` plus `sort`/`elevation`/`restrictions`; drawings use a
  `shape` object with a flat point array; ambient lights nest their emission
  settings under `config`.
- Mirrored tiles and tokens are written as a negative texture scale rather than
  a negative width/height, which v13 rejects.

### Game system data (ADR-006, ADR-007)
- Character subclasses are emitted as their own `subclass` documents linked to
  the class by identifier, instead of `system.subclass` on the class item. That
  field stopped being read in dnd5e 2.1, and because Foundry silently discards
  unknown keys, every conversion since had dropped the subclass with nothing
  logged. Class items now also carry the `identifier` the link relies on.
- Species and backgrounds are emitted as `race` and `background` documents,
  which is what dnd5e has read since 4.0. Converted characters previously
  arrived with empty "Add Species" and "Add Background" slots even though the
  Roll20 data was present.
- `details.race`, `details.background` and `details.originalClass` now hold the
  id of the document they refer to. dnd5e keeps these links up to date through
  document hooks that only run inside Foundry, so an imported world never had
  them set; `originalClass` in particular was written as an empty string.
- Characters with no species or background — Roll20 area templates converted as
  actors, for instance — get no documents rather than ones named `""`.

### Correctness
- Add the `--disable-module-items` option. The conversion code honoured it but
  the flag was never declared, so it could not be used.
- Exit with a non-zero status when a conversion fails, so scripted and batch
  conversions can detect failures.
- `--folder-as-items` now replaces the default "Magic Items" folder instead of
  appending to it, making the default possible to opt out of.
- `--enable-fog` and `--disable-fog` are now mutually exclusive rather than
  silently accepted together with undefined precedence.

### Robustness
- Asset downloads now use a timeout and bounded retry with backoff; a stalled
  connection no longer hangs the entire conversion.
- Download failures report their actual cause instead of being silently
  swallowed, so a network error is distinguishable from a missing image.
- The asset cache stores file paths rather than response bodies; it previously
  grew to the full size of a campaign's media and could exhaust memory.
- Asset destinations are verified to stay inside the output directory.
- Fix the Windows executable doing nothing when launched. eel resolves its web
  root through `sys._MEIPASS`, a PyInstaller attribute, whenever `sys.frozen` is
  set; cx_Freeze sets `sys.frozen` without it, so `eel.init()` raised and the
  GUI module failed to import. The program then silently fell through to command
  line parsing and exited with a usage error no one could see.
- A failed GUI launch now reports the underlying error instead of being
  swallowed and printing an argparse usage message.
- Launch the bundled Electron shell through eel's current `cmdline_args`
  interface; the `custom_callback` hook it replaced no longer exists.
- Resolve `client/dist` and the bundled Electron relative to the executable
  rather than the working directory, so the program works when started from
  somewhere other than its own folder.
- Compendium pack load failures are logged instead of being silently ignored,
  the most common cause of "my character sheets are empty".

### Project
- Add a `pytest` suite and a GitHub Actions CI workflow (ADR-004).
- Add `docs/adr/` recording the architectural decisions.
- Replace the stale py2exe `Makefile` with working cx_Freeze targets.
- Add `requirements.txt` pinning the exact dependency versions the build is
  known to work with, and note the Electron runtime the Windows build needs
  (ADR-001).
- Mark the unused PyInstaller `R20Converter.spec` as deprecated; `setup.py`
  with cx_Freeze is the supported build path.
- Import `matplotlib` only where it is used, so the test suite no longer needs
  the frozen build's heavy dependencies in order to import `entities`.
- Add `.gitattributes` normalising line endings, after a change was committed
  with the opposite convention and turned a 45-line diff into a 5,605-line one.

## v0.8

- Port database format to FVTT 0.4.4/0.4.5
- Convert Roll20 macros into chat macros 
- Restore each user's macro hotbar to match their macrobar on Roll20
- Add support for converting the chat log
- Convert roll templates for the OGL sheet so character sheet rolls from chat will appear as they did on Roll20, including tooltip support
- Enables [Chat Autoloader](https://gitlab.com/moerills-fvtt-modules/chat-autoloader) FVTT module by default (module by @Moerill).
- Fix permissions for actors that are in player's journal to limited instead of observer, to better match the behavior on Roll20
- Add support for horizontal mirroring of tokens
- Add checks against invalid roll tables and decks
- Prevent NPC weapons that match loot item names (such as a shovel or torches that deal 1 damage) from becoming loot and removing their damage values
- Make the 'Auto Doors' option enabled by default in the GUI

## v0.7

- Port Core data to 0.4.x
- Port Actor data to 0.4.x
- Port Item data to 0.4.x
- Port Command line options/behavior and GUI to use 0.4.x data and auto discover of FVTT data path on the system
- Fix some scenes that could have drawings with an invalid author if the player that drew it was deleted from the campaign
- Add support for flipped tiles without needing to use drawings
- Add support for sort order of entities using core feature without the use of entityorder module
- Better support for shaped sheet character conversions
- Add support for lair and regional effects for NPCs
- Nearly rewrote the entire character sheet data migration making it much more stable and reliable and accurate in how character data is converted
- Use rollable table names for multi-sided tokens to name the actor side filenames more accurately
- Add support for roll tables
- Add support for converting decks into Items and associated Roll Tables
- Add option to force all scene backgrounds to be converted into tiles
- Add option to force all token bars (bar 1 or bar 2 or both) to be linked to the actor HP
- Lock all tiles/drawings from the map layer

## v0.6.4

- Fix various small crashes related to character sheets having invalid data

## v0.6.3

- Fix a crash when importing a spell/item from SRD compendiums that are cross linked from a journal entry

## v0.6.2

- Fix a crash when converting with --export-as-module and --no-duplicate-actor-items options together

## v0.6.1

- Fix crash if an Roll 20 item's modifiers is badly formatted
- Fix error in FVTT if a converted character didn't have a class name set.

## v0.6

- Add --folder-as-items option to allow conversion of a handouts folder into items
- Add proper support for drawings, using the FVTT drawings database (Fixes unicode character conversions)
- Add --images-as-drawings option to convert all Roll20 graphics into drawings instead of tiles
- Add support for flipped graphics
- Character items will also be exported as Items in the sidebar for re-use.
- Fix many small issue in how actor items, weapons, traits, feats were getting converted
- Add experimental support for the Shaped Sheet template
- Fix conversion of worlds with unicode characters in their name
- Show conversion errors in the GUI if a crash happens
- Split languages and armor proficiencies if written as a single proficiency in Roll20, separated by commas
- Fix path separator issue in module creation so a module generated on windows will work on a linux system
- Fix a bug where if a scene name starts with '/', it would not write its asset files in the correct path
- Add ability to disable conversion of specific packs when exporting to a module
- Add protection against long file paths so all resources can be accessed on the filesystem
- Convert orphaned handouts which do not show in the journal folder data but appear on the root journal.
- Add character classes to actor conversion
- Add personality traits/bonds/flaws/ideals to the character Bio
- Fix actor's XP, item attacks and damages
- Fix NPC damage mods getting doubled when an attack is considered a weapon (due to FVTT adding the str/dex modifier)
- Fix a character imported from Roll20 compendium having its token emit light by default
- Update to FVTT 0.3.8 database schema 

## v0.5

- Add character apperance/backstory/treasure/allies to the BIO
- Add option to export the campaign as a module
- Add a simple GUI 
- Add --cleanup-scenes option to clean walls/tokens/tiles outside of the map boundaries

## v0.4

- Added actor conversion support
- Split off from R20Exporter
- Update to FVTT 0.3.5 database schema
- Port to Python 3 for better internationalization/unicode support
- Add --json option to parse a campaign.json and download the resources directly
- Fix issue with fonts not loading properly
- Add --walls-around-map option

## v0.3

- Add support for multisided tokens
- Add folder and entity order
- Fix HP bar on tokens

## v0.2

- Add fonts for proper text conversions
- Add minimum wall length and maximum angle options
- Add option to override title
- Add option to disable conversion of archived handouts/actors/scenes

## v0.1

- Initial release
- Support for converting scenes, tokens, journal entries, combat and jukebox entities
- Add internationalization support and Windows support
