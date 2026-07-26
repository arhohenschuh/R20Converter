# Changelog

## Unreleased

**Targeting Foundry VTT v13.** See `docs/adr/` for the decision records behind
these changes.

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
