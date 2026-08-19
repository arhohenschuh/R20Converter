# Changelog

## Unreleased

- Preserve GM-only chat visibility when R20Exporter emits a GM whisper as `type: hidden` with
  `original_type: whisper`, or a private roll as `type: secretrollresult` with `secret: true`.
  Hidden GM whispers now become Foundry whispers to every GM; secret roll results retain their
  rendered message type and become GM-only. Ordinary hidden/general messages remain public. The
  full suite passes 787 tests with 21 optional `plyvel` skips.
- Normalize literal dots and leading dollar signs in nested world-document keys before NeDB
  serialization, while preserving module-pack keys and aborting on normalization collisions. This
  prevents copied compendium provenance keys such as `beyond5e-2.5.0` from blocking Foundry's
  NeDB-to-LevelDB migration. The full suite now passes 790 tests with 21 optional `plyvel` skips.
- Emit ChatMessage `rolls` as structured Foundry 14 Roll objects using evaluated `terms` rather
  than JSON strings or the obsolete `parts` schema. Preserve historical formulas, totals, dropped
  dice, evaluated modifier contributions, and grouped-roll formulas. Also clear Roll20 HP prose
  that cannot satisfy dnd5e FormulaField validation and separate a lone damage type from a weapon
  formula such as `1d6 + piercing`. The full suite passes 799 tests with 21 optional `plyvel` skips.
- Persist `dnd5e.rulesVersion` as the JSON string `"legacy"` in converted worlds. dnd5e 5.3.3
  defaults a missing setting to `modern`, which silently runs 2014 content under 2024 rules. The
  full suite passes 799 tests with 21 optional `plyvel` skips.

## v1.10.1

**Corrects the unsafe colour classifier shipped in 1.10.0.** The per-page native-door
guard was right; frequency ranking was not. Three immutable source controls falsified it:

| Page | Source colours (segments) | 1.10.0 did | 1.10.1 does |
| --- | --- | --- | --- |
| Dragon Heist, Theater ×2 | orange 195, blue 146 | made **blue walls** doors | orange doors |
| Hidden Shrine, Temple | blue 272, green 1, orange 1 | green door, orange **secret** | orange ordinary door |
| Sunless Citadel, Fortress Bottom | blue 473, orange 59, `transparent` 40 | `transparent` **secret doors** | orange ordinary doors; transparent unchanged |

The corrective policy was agreed through a seven-round cross-model review and verified
against a hash-pinned baseline of 18 official-module exports: **314** walled pages, **155**
legacy-colour pages, **3,929** minority-colour segments, and **84** rank-3+ segments the old
code would have turned into secret doors.

- Explicit `--door-color` / `--secret-door-color` still win.
- CSS colour tokens are normalized before comparison (`rgb()` / `rgba()` / shorthand hex),
  while non-colour sentinels such as `transparent` remain distinct.
- On pages without native door objects, only Roll20's demonstrated canonical orange
  `#ff9900` is inferred automatically, regardless of frequency.
- Unknown custom palettes are left as walls with a warning; the converter refuses to guess.
- **Secret doors are never inferred.** They require an explicit `--secret-door-color`.
- Pages with native door objects keep those doors and report normalized non-blue residue
  without converting it. That residue remains scheduled evidence work, not silent loss.
- `--auto-doors` is deprecated and warns; it no longer enables the unsafe heuristic.
- A post-cleanup conservation assertion aborts if classified ordinary/secret door counts do
  not equal the emitted counts.

Real controls include Theater Spring/Winter, Hidden Shrine Temple, Sunless Fortress Bottom,
Converted Windmill's near-orange `#e69138`, Ravenloft's mixed hex/`rgb()` blue, Twisted
Caverns, Hrakhamar, Sargauth, Cragmaw and Crystal Labyrinth. Restoring the 1.10.0 algorithm
makes **8** of those assertions fail. The conservation helper has its own fail-closed control.

The 1.10.0 binary remains available as history but must not be used for Tyranny of Dragons or
another conversion. No campaign/module data is changed by this release.

Suite: **785 → 805 tests**.

## v1.10.0

**Legacy doors are recognised again.** Roll20's legacy dynamic lighting had no door
objects — a door was a wall drawn in a different stroke colour — and recognising that
required `--auto-doors`. The GUI defaults that flag **on**
(`client/src/components/AdvancedOptions.vue`: `autoDoors: true`); the CLI defaults it
**off**. The same campaign therefore kept or lost every door depending on which one you
ran. See [B058](docs/bugs/B058-legacy-dl-doors-become-walls.md).

Measured across the archived exports: **272 of 392 walled pages** encode doors as
coloured wall paths, and **11 of 22 campaigns carry no door objects at all** — Waterdeep
Dragon Heist on **40 of its 41** walled pages, Storm King's Thunder on 19 of 25, plus
Dragons of Icespire Peak, Ghosts of Saltmarsh, Princes of the Apocalypse, Out of the
Abyss and all seven TotYP modules. Every door in those converted as a solid wall.

The page now says which encoding it uses, so nobody has to pass a flag:

| Page | Behaviour |
|---|---|
| carries `doors` objects | trust them; **never** colour-classify |
| no `doors`, more than one wall colour | legacy encoding — classify by colour |
| no `doors`, one colour | nothing to infer |

The second rule is why a blanket default would have been wrong. *Dungeon of the Mad
Mage*'s Crystal Labyrinth has 55 real door objects **and** five wall colours; classifying
it would have turned 39 green and 1 black wall segments into secret doors. One module can
mix both — that same module's Twisted Caverns has no door objects and 12 orange segments
that genuinely are doors.

`--no-auto-doors` disables inference entirely, and an explicit `--door-color` still wins.
`--auto-doors` is now a no-op kept for compatibility.

Suite: **772 → 785 tests**.

## v1.9.0

**Walls restrict movement again.** A wall drawn on Roll20's dynamic-lighting layer
now converts with `move: 20`, so Foundry draws it yellow and tokens stop at it.

`move` used to come from the page-level `lightrestrictmove` flag. Measured across the
24 archived exports, that field is `true` on **52** pages and `null` on **616** — and
is **never once written as `false`**. An "off" state that cannot be distinguished from
"never set" is not a boolean, and Jumpgate stopped maintaining the field entirely; the
live setting there is the per-barrier `barrierType`, which is `wall` on 30,013 of the
32,087 wall paths in those exports.

Reading it as a boolean meant **136,884 of 248,169 wall segments (55%)** converted as
non-blocking. On 358 of 409 walled pages *every* wall was purple. See
[B057](docs/bugs/B057-walls-do-not-restrict-movement.md).

A legacy (non-Jumpgate) campaign can still say no: an explicit `lightrestrictmove:
false` is honoured. `--no-restrict-movement` forces the old behaviour for any campaign;
`--restrict-movement` still works and is now the default.

**Also in this release — B056 is finally complete.** 1.7.7 moved extension derivation
into `Entity.assetExtension` and wired it into `downloadResource`, the path an asset
takes when it is *missing* from the export. Assets that are *present* go through
`copyZipFile`, which kept its own inline derivation, so the repair never reached the
common case.

Measured across the archived exports: **139 zip members** in five campaigns carry a
name Foundry will not draw — *Dungeon of the Mad Mage* 74, *Storm over Savage
Frontier* 48, *Lost Mine of Phandelver* 11, *Curse of Strahd* 4, *Wardens of the
North* 2. The original bug record put the population at 54 across two campaigns; it
was measured on the two worlds being repaired at the time, not on the fleet.

The two extensions are not the same value and conflating them was the defect.
R20Exporter names the zip member from the raw URL, so the **lookup** must keep
`.jfif` and any `&cb=` fragment; the file **written to disk** must not. They are now
separate variables. A negative control confirms the new tests fail against the old
derivation.

Suite: **758 → 772 tests**.

## v1.8.0

Converted **modules** keep their folders. Until now they did not: four places
cleared `folder` whenever `--export-as-module` was set, and the module branch
never built a folder tree at all, so an adventure imported as one flat list per
pack. Worlds were unaffected — they build the same tree from the same Roll20
`journalfolder` data and always have.

The cost of that was measured on the 18 adventure modules this converter
produced: **5,108 journal entries, every one of them in a single flat Handouts
folder**. Putting them back afterwards took a separate tool chain, an offline
gate, a live import gate and 18 re-releases, and recreated **531 folders** the
converter had already computed and then discarded. Preserving every document is
not the same as preserving the campaign, and only one of those was being checked.

Folders are now written into each pack under `!folders!`, scoped to the type
that pack holds, so a journal pack carries journal folders and nothing else.
Ids come from the Roll20 ids, so re-converting is still byte-stable. Empty
branches are still dropped rather than shipped. See
[ADR-010](docs/adr/ADR-010-module-pack-folders.md).

**Order is part of the tree.** Foundry defaults `Folder#sorting` to `"a"`, so a
perfectly restored hierarchy still comes out alphabetical — *Part 3* above
*Part 12*, "Introduction" somewhere in the middle. Generated folders now declare
manual sorting and carry explicit `sort` values. While pinning that down, two
siblings turned out to share a sort value: the old expression read
`100000 * (index if index else 1)`, so index 0 and index 1 both produced
100000 and their order was left to chance. Worlds get that fix too.

**Scenes: `--scene-folders`.** Roll20 has no folders for pages — the journal has
`journalfolder`, pages are a flat list — so there is nothing to restore and
chapter structure has to come from somewhere. It comes from an explicit
manifest, not from guessing at page names, which is right for one adventure and
quietly wrong for the next:

```json
{
  "schema": "r20converter-scene-folders/v1",
  "root": "Against the Giants - Scenes",
  "folders": [
    {"name": "Steading of the Hill Giant Chief",
     "scenes": ["Upper Works", "The Dungeons"]},
    {"name": "Glacial Rift of the Frost Giant Jarl", "scenes": ["Rift Map"]}
  ],
  "rootScenes": ["Start"]
}
```

Scenes are named the way they appear in Roll20, or `{"id": "-Abc…"}` when two
pages share a name. A reference that matches no page, matches two, or is claimed
by two folders **aborts the conversion** — a mis-filed scene is invisible in a
module that otherwise looks organized. Pages the manifest does not mention stay
at the root, so a partial manifest organizes what it names and cannot lose
anything. Without the option nothing changes. See
[ADR-011](docs/adr/ADR-011-scene-folder-manifest.md).

The manifest is CLI-only for now; the GUI does not expose it yet.

Suite: **729 → 758 tests**. The frozen Python 3.8 environment with native
`plyvel` passes **758/758**, covering the folder tree, pack layout, CLI option
and every fail-closed manifest rule. Where `plyvel` is unavailable, the same
suite reports **737 passed / 21 skipped**; the `!folders!` write contract still
runs there through a stubbed binding instead of disappearing with the native
LevelDB tests.

## v1.7.7

Fixes **B056**: assets were stored under the extension the Roll20 URL advertised, so files
landed on disk that Foundry silently refuses to draw.

Only a `?` fragment was stripped, so a cache-buster after `&` survived into the filename —
**52 assets** across *Storm over Savage Frontier* and *Curse of Strahd* were written as
`….svg&cb=5`. And `.jfif`, an ordinary JPEG container Roll20 serves, is not in Foundry's
`CONST.IMAGE_FILE_EXTENSIONS`; the *Lakeside* map on *Wardens of the North* converted, was
written to the right path, passed G07/G09/G10 — and never appeared.

Extension derivation moves into `Entity.assetExtension`, which keeps only the leading
alphanumeric run and maps the aliases Foundry does not list (`jfif`/`jpe`/`jif`/`jfi` → `jpg`,
`tif` → `tiff`). `RENDERABLE_EXTENSIONS` records the client's accepted set next to it.

Note for anyone repairing an existing world: the two Wardens files' magic bytes showed one is
actually **PNG** despite the `.jfif` name, so rename by content, not by extension.

## v1.7.6

Fixes **B055**: `Items.addToFolder` advanced its directory index only for sub-folders, so
handouts, characters and PDFs consumed no index and every later folder was numbered low.
*Storm over Savage Frontier* derived `029 - Magic Items` where the export holds
`074 - Magic Items`; *Wardens of the North* derived `005` against a real `083`.

The handout and character branches sat behind `elif is_items_folder`, which describes the
folder being walked rather than the child, so for every ordinary folder they never ran.
Inside an items folder there was still no `pdf` branch — B053 verbatim, which this walk
never received. Numbering is now unconditional and matches the exporter; item *creation*
stays gated on `is_items_folder`.

No shipped world needs repairing: every archived export carries `export_report.json`, and
the 1.7.4 manifest lookup already resolved these assets by URL. As with B049 masking B053,
the workaround hid the defect — the derived path is the fallback for legacy exports, and it
was wrong.

`Folders.addJournalFolder` was audited and is unaffected (it numbers for sidebar sort
order, not zip paths). `playlists.py`, `scenes.py` and `tables.py` have no such walk.

## v1.7.5

Fixes **B054**: a magic armour's enchantment overwrote its base AC, so a Half
Plate +2 converted with `armor.value = 2` instead of 15.

Roll20 lists both under the same name in `itemmodifiers` —
`"Item Type: Medium Armor, AC: 15, AC +2"` — and the parser assigned each entry
into a flat dict, so the bonus landed on top of the base and `int("+2")` became
the armour value. The damage is invisible until the armour is equipped and the
sheet recomputes, which is why it survived three published worlds.

A repeated modifier whose value is signed is now kept under `"<key> bonus"`, and
the bonus is emitted as `armor.magicalBonus` rather than being discarded. Items
whose only `AC` entry is a bonus — a Ring of Protection — are unchanged.

## v1.7.4

Fixes **B053**: a PDF in the journal tree shifted every later zip path by one,
so 111 assets on *Dragoncoast Danger* were looked for in
`journal/006 - Handouts/` while the export held `journal/007 - Handouts/`.

Roll20's `journalfolder` is one ordered array mixing folders with loose entity
ids, and the exporter numbers **every** sibling it writes. `addToFolder`
advanced its index only for folders, handouts and characters, so an entity type
the converter does not consume — a PDF — was skipped silently and everything
below it was numbered one low, whole subtrees included.

The interesting part is why it took two days to find. B049's download fallback,
added the day before, catches a zip miss and refetches the asset from its
original URL. It worked: 112 of the 116 came back, the world looked right, and
a systematic path bug therefore presented as intermittent CDN trouble. The
fallback was masking the very defect it was compensating for. It is kept — four
of those assets really were absent, and the exporter's own report confirms it —
but `copyZipFile` now counts misses and says so once past 25, because a
workaround that succeeds quietly is a workaround that hides its cause.

Three changes:

- `Journal.addToFolder` counts the siblings it skips, and `Entity.findID` gained
  a `"pdf"` case so they can be recognised. The `pdf` lookup is placed last, so
  no id that already resolved changes meaning. This alone repairs **legacy
  exports**, which carry no manifest and can only be handled by derivation.
- R20Exporter 0.14.0+ ships `export_report.json`, recording the path it actually
  wrote for every asset. `loadExportReport` builds a URL → path map at startup
  and `copyZipFile` consults it before its own derivation. Derivation cannot
  know about entity types the converter does not consume; the manifest does not
  have to guess. This is a second line of defence, not the repair — **18 of the
  21 exports in the local archive predate the manifest**, so derivation still
  carries most of the work.
- `noteZipMiss` warns once past 25 misses when no manifest is present.

Order is now manifest → derivation → download.

Verified by re-converting *Dragoncoast Danger* from both exports: **116 zip
misses → 5** with the 1.0.0 export (488 URLs resolved from the manifest) and
**116 → 5** with the 4 Aug export that has no manifest at all. The residual five
lines are four distinct assets, and `export_report.json` independently reports
`failed: 4` for exactly those URLs.

The same derivation pattern lives in `items.py`, `playlists.py`, `scenes.py` and
`tables.py`. Only the journal path is confirmed defective; the others are
recorded in B053 as unaudited.

## v1.7.3

Fixes a regression in 1.7.1 that broke **every** conversion.

The conversion log added in 1.7.1 opened its file lazily and created the output
directory on the way, with `makedirs(..., exist_ok=True)`. `convert()` logs its
opening line before anything else, so the log created the directory a single
statement before `convert()` tried to create it itself — and `convert()` uses a
bare `makedirs`, which raises when the directory already exists:

```
FileExistsError: [WinError 183] ... 'Data/worlds/<id>'
```

The obvious repair — relaxing that `makedirs` to `exist_ok=True` — would have
been the wrong one. It is not merely creating a directory; it is the check that
stops a conversion from writing into a world that already exists. The CLI
guards the destination separately and offers `--overwrite`, but the GUI does
not, so for GUI users that one call is the only thing standing between a typo
and an overwritten campaign. Relaxing it would have traded a loud crash for a
silent loss.

The log now buffers its lines until the output directory exists, and never
creates it. Nothing is lost: the buffered lines are written as soon as the
directory appears, so a finished conversion still carries a complete log
starting from its first line.

## v1.7.2

Player characters convert with working darkvision (B044, take two).

1.7.0's fix derived a PC's darkvision from the night-vision radius configured on
their Roll20 token. That was already known to be unsound when it shipped: a High
Elf in the reference campaign carries a 5 ft token radius against the 60 ft the
race actually grants, and a "working" derivation would have written the wrong
number instead of an honest zero.

The corrected fix drops the token radius entirely and matches the Roll20 race
name itself — the same string already written onto the character's `race`
document — against a small, hand-verified table of SRD 2014 darkvision ranges.
This mirrors the regex table already field-tested in the post-conversion
pipeline: a High Elf or Half-Elf now converts to 60 ft, a Drow to 120 ft, and a
Human, Dragonborn or Halfling correctly to 0. A race the table does not
recognise — homebrew, or a name it does not cover — is left at 0 rather than
guessed.

This is deliberately *not* a compendium lookup. `createItemOrigin` still emits
the `race` document verbatim, with no lookup at all, exactly as ADR-007 already
decided: SRD 5.1 has no `Variant Human` or `Standard Human` entry and `High Elf`
is a subrace rather than a top-level one, so matching the document itself would
reopen a trade-off that was already rejected for good reason. Only the numeric
darkvision range is derived, from the name string, never the document's
identity or features.

Suite: 633 -> 644.

## v1.7.1

Every conversion now leaves a `conversion-log.txt` in the folder it produced.

The log previously existed only on stdout (CLI) or inside the Electron window
(GUI), so a finished world carried no record of its own conversion — and the list
of compendium items that could not be matched, which is the most useful thing in
it, had to be copied out of the UI by hand before it was lost.

Lines are written verbatim and flushed one at a time, so a run that crashes still
leaves the log that explains why. Any failure to write it disables the file and
lets the conversion continue: a log is worth less than the run it describes.

> **Known limitation, measured on a real campaign.** Player characters still
> convert with `darkvision: 0`. Roll20 stores no senses block for a PC, and the
> only nearby signal — the token's night-vision radius — is not the same thing: in
> *Wardens of the North* a High Elf who should have 60 ft carries a 5 ft token
> radius. The converter declines to invent a value from it. Setting PC senses is
> therefore a post-conversion step; see the pipeline document.

## v1.7.0

Tokens are no longer converted blind, and player characters keep their senses.

Three defects, found by chasing one symptom: on a fully dark map in a converted
world, player characters could see nothing at all — not even a light placed next
to them.

**Sight and light arcs (B045).** Roll20 records unrestricted vision by *omitting*
a field-of-vision limit, and the converter turned that absence into `angle: 0`.
Foundry reads `sight.angle` as the aperture of a cone and defaults it to 360, so 0
is not "unlimited" but a **zero-degree cone** — the exact opposite. Every affected
token was blind no matter what its senses said. The same mistake applied to
emitted light. Both now convert to 360, an out-of-range or unparseable angle falls
back to 360 rather than 0, and a genuinely narrowed cone is still preserved along
with the rotation flip that goes with it. Measured on *Wardens of the North*: 394
of 394 prototype tokens carried a zero-degree cone.

**Player-character senses (B044).** `createAttributeSenses` parsed senses only for
NPCs, so no code path could ever give a player character darkvision. This is not
cosmetic: a vision module derives a token's vision from the **actor's senses**, not
from the token's sight range, so a PC with darkvision 0 falls back to light
perception and sees only what is already lit. Characters now take their darkvision
from the night vision configured on their Roll20 token, ignoring the one-foot
value that only means "has sight, no radius".

Senses are also emitted in the shape dnd5e 5.3 actually declares —
`senses.ranges.*` rather than the flat keys. The old shape survived on a
compatibility shim that dnd5e removes in 6.1, at which point NPC senses would have
broken too.

**NPC special senses (B046).** `passive Perception` leaked into
`senses.special`, because the guard compared case-sensitively against Roll20's
capitalised text while the loop removed entries from the list it was iterating —
skipping whatever followed. Found by a regression test written for B044 rather
than by reading the code.

Suite: **594 → 624**.

## v1.6.1

Player characters convert with a friendly token disposition.

`disposition` was hardcoded to `-1` (hostile) for every token, so dragging a PC
onto a scene produced a red, hostile-looking token. Roll20 has no disposition
concept, but it does distinguish a character sheet from an NPC sheet, so the
token now follows the actor: characters are friendly, everything else stays
hostile.

Both sides are covered — the actor's prototype token, and tokens already placed
on a scene, which look up the actor they represent. Placed tokens with no actor
behind them (map decoration, markers) are left hostile, since nothing
identifies them as anything else.

## v1.6.0

`--enable-token-vision`, with a matching "Enable token vision" advanced setting,
switches sight on for every token and enables token vision on every scene.

Roll20 only records sight for a token whose lighting was configured, so most
tokens convert with sight off. A vision module — vision-5e and friends — derives
the range from the actor's own senses, but only for tokens whose sight is
switched on, so without this the module has nothing to act on.

The scene flag and the token flag are forced together on purpose: a scene with
`tokenVision` off ignores every token's sight setting, so forcing one without
the other achieves nothing. The converted sight *range* is left alone, which
keeps a sensible fallback for anyone not running a vision module.

Measured on *Wardens of the North*: 22 of 79 scenes and 127 of 1,978 placed
tokens had vision before; all of them do with the option on.

## v1.5.1

- An entry Roll20 left unnamed is converted as `Unnamed Weapon`, `Unnamed
  Feature`, `Unnamed Spell` and so on, and the actor holding it is reported.
  The old placeholder was the literal `<no name>`, which sorts to the top of
  every list, says nothing about where it came from and matches no compendium
  entry. Found by diffing a fresh conversion against the same campaign after a
  manual repair pass: 11 of them, which the repair had deleted by hand.
- `--package-version` sets the version stamped on the generated world or module
  manifest. Publishing a release as one version while its manifest declares
  another is the kind of version-lie the rest of this project exists to remove.

## v1.5.0

Content can now be matched against a **custom compendium module**, not just the
game system's own packs.

- `--custom-compendium <module-id-or-path>`, with "Use a custom compendium" in
  the GUI's advanced settings. It takes a **module id** as found under
  `Data/modules` — portable between machines, and resolvable because the data
  directory is already detected — or a path for a module kept elsewhere.
- `--custom-compendium-mode {additive,replace}` (default `additive`): join the
  system packs, or stand in for them.
- `--custom-compendium-precedence {custom,system}` (default `custom`): which
  source answers first when both hold something of the same name. Only
  meaningful in additive mode, and the GUI hides it otherwise.
- Documents are classified by their **own type**, not by the pack they sit in.
  A module's pack names are not trustworthy: Beyond5e keeps its class features
  in `item-3-classes` and ships an empty `item-5-class-features`, exactly as
  dnd5e keeps its 2024 features in `classes24`.
- Matched documents keep their own artwork, which often lives in a *separate*
  assets module. The converter now names those modules, because the alternative
  is discovering broken images long after the conversion.

Measured on *Sunless Citadel* with Beyond5e (4,104 usable documents against the
SRD's 1,769): matches rise from 114 of 357 to 136.

## v1.4.2

The SRD edition options are now labelled **2014 (Legacy)** and **2024
(Modern)**.

1.4.0 labelled 2014 "matches Roll20 campaigns" and justified the default that
way in the GUI, the `--srd-edition` help and the `foundry.py` comment. That was
wrong: Roll20 campaigns can be built on either edition. 2014 remains the
default because it is the larger body of existing material — a default, not an
assumption about the input.

## v1.4.1

- The SRD edition selector moves from Advanced Settings to the main page,
  directly under the World/Compendium toggle. It decides which content a
  conversion is matched against, which is a headline choice rather than a
  fine-tuning one, and Advanced Settings is collapsed by default so it was
  easy to miss.
- The store now carries `2014` as its default, so a conversion started without
  ever opening the selector sends an explicit edition instead of `undefined`.
  The converter also treats an unset value as the default rather than warning
  about an unknown edition.
- `docs/BUILD-windows-arm64.md` records what ships (x64 throughout), why the
  x64 build is expected to run under Windows-on-ARM emulation, and the three
  upstream blockers to a native ARM64 build — chiefly that Python 3.8 has no
  Windows ARM64 distribution.

## v1.4.0

An SRD edition switch, and a correctness fix in the pack reader 1.3.0 shipped.

- `--srd-edition {2014,2024}`, and a matching selector in the GUI's advanced
  settings. **Defaults to 2014**: a Roll20 campaign's sheets are 2014 content,
  and the two generations share spell and item *names* while differing in text
  and mechanics, so matching against 2024 replaces an item with a different
  edition of the same name.

  Measured on *Sunless Citadel*: 2014 matches 114 of 357 items and 2024 matches
  110, with 92 in common. The difference is mostly class and monster features
  (12 under 2014, 6 under 2024) — `Multiattack` and `Protection` resolve only
  against the 2014 packs, `Chromatic Orb` only against the 2024 ones.

  The pack names behind each edition were read from the packs themselves, not
  inferred: `classes24` holds classes *and* their features, so it serves two
  roles and is read once, and the 2024 monsters are in `actors24`.

- **Folders are no longer read as documents.** A Foundry pack keeps its folder
  tree under `!folders!`, and those entries carry a `name` — so the reader
  added in 1.3.0 saw a folder called "Wand" as an item called "Wand", and a
  lookup could match one. This inflated the 2014 pack read from 1,769 documents
  to 1,834 and could have attached a folder's data to a converted item.

## v1.3.0

Compendium enrichment works again on current installs (B031, fully fixed).

dnd5e has shipped LevelDB compendium packs since 3.0, and the converter read
only NeDB files — so on any current install no pack loaded, every item kept its
Roll20 icon and description, and journal compendium links stayed Roll20 URLs.
1.0.1 made that visible; ADR-009 then added the LevelDB dependency for writing
module packs, and reading them is the same dependency.

- Pack loading prefers the LevelDB directory and falls back to a NeDB file.
- The reader works the collection out from the key prefixes rather than being
  told it. A system pack is named for its content, not its document type —
  `spells24`, `actors24` — so the name is no help.
- The 2014 SRD packs are used rather than the `*24` ones: a Roll20 campaign
  predates the 2024 rules, and matching against a 2024 document of the same
  name would swap in a different edition of the spell.
- The "cannot read LevelDB" warning now only appears when LevelDB support is
  genuinely missing, and names the import error that caused it.

Measured on a real dnd5e 5.3.3 install: 1,851 documents across five packs read
in under a second, and a *Sunless Citadel* conversion matched 114 of 357 items
— 68 spells, 34 weapons, 12 feats — which now arrive with system icons and
their compendium activities.

## v1.2.2

Two follow-ups to 1.2.1, both found by running the new detection against real
installations rather than fixtures.

- A relative `dataPath` is resolved against the `Config` directory holding it.
  A portable install writes `".."`, meaning the folder its config sits in;
  resolving that against the working directory rejected an install that was
  perfectly good.
- `Config/options.json` now takes precedence over the directory itself looking
  like a data path. An install can hold a stale `Data` tree while its config
  redirects elsewhere, and Foundry follows the config — so checking the
  directory first meant detection stopped at the wrong install.

## v1.2.1

Foundry data directory detection no longer takes a path on trust.

- A candidate is only accepted if it actually contains `Data/systems`. A stale
  `Config/options.json` — one copied from another machine, or a default install
  pointing at itself while the real data lives with a portable copy — was
  followed silently, and the conversion then ran with no compendium enrichment
  and no explanation of why.
- `--fvtt-data-path` now accepts an *installation* directory as well as a data
  directory. A portable install keeps `Config/options.json` beside the
  application and its data on another drive entirely, so pointing at the folder
  the user actually knows now works; the `dataPath` inside is followed and
  validated.
- When no usable directory is found the converter says which path it tried and
  how to override it, instead of continuing quietly.

## v1.2.0

Module exports now write Foundry LevelDB compendium packs directly instead of
NeDB files (ADR-009), removing the import-and-re-export round trip from the
publishing pipeline.

- `--export-as-module` writes `packs/<name>/` LevelDB directories. The encoding
  was read out of a published module running on Foundry 14.365 rather than
  guessed: primary documents keyed `!<collection>!<id>`, embedded documents
  keyed `!<collection>.<embedded>!<parent>.<child>`, plain uncompressed JSON,
  and the parent holding each embedded collection as an array of ids.
- Worlds still write NeDB deliberately. Foundry's world migration is automatic
  and was measured lossless, so it does not justify a native dependency.
- `plyvel` is optional. It is bundled in the frozen build, so every `.exe` user
  gets LevelDB packs; a source install without it falls back to NeDB and says
  so rather than failing.
- Rewriting a pack removes the previous one first. LevelDB merges by default,
  so converting twice into the same directory would otherwise leave deleted
  documents behind as orphans Foundry still shows.
- Fixed a latent bug in the pack-name derivation: `re.sub(".db", "", name)`
  used an unescaped dot, so a name like `adb.db` collapsed to the empty string.

## v1.1.0

Closes every remaining finding of the 2026-08-03 audit — B029, B030, B036 and
B039–B042. A minor rather than a patch release because the emitted document
shapes change: containers change item type, NPC casters gain slot overrides and
a caster level, and activities gain consumption targets.

With this release every bug in `docs/bugs/` is either fixed or explained. The
two that are not fixed — B031 and B043 — are blocked on the same decision, and
say so.

### Data loss
- Activating a limited-use item spends a use. The activity carries a
  `consumption.targets` entry of type `itemUses`; it previously carried a copy
  of the item's own `uses` pool and no target at all, so the sheet showed two
  pools and using the item decremented neither.
- NPC spellcasters arrive with the slots their statblock prints. `spells.spellN`
  emits the declared `{value, override}` — `max` is derived and was dropped on
  load — and the caster level is parsed from the Spellcasting trait into
  `attributes.spell.level`, which is the only thing slot progression reads.
- Innate spells keep multi-digit use counts. The count was read with `(\d)`, so
  "10/day" became one use and, because the period group then failed against the
  second digit, one use that never came back.

### Schema conformance
- Spell slot counts are emitted as numbers. Both fields are `NumberField`s and
  the sheet stores them as strings; 167 of them were being handed to Foundry to
  cast, in a converter whose whole premise is not leaning on that.
- Containers emit `type: "container"` and the declared `capacity` shape.
  `backpack` is not rejected — dnd5e rewrites it and sets
  `persistSourceMigration`, queueing every container for a rewrite, which is the
  outcome ADR-008's gate measures to be zero.
- NPC creature types are split into `value` / `subtype` / `swarm`, with the head
  word validated against `CONFIG.DND5E.creatureTypes` and anything unrecognised
  routed to `custom`. "humanoid (goblinoid)" stored whole matched nothing that
  looked it up, so a converted goblin was not a humanoid to a favored-enemy
  check or a compendium filter.
- `"charges"` is gone from the recovery-period whitelist. It is a *consumption*
  type in 5.x, and `period` is unvalidated, so it would have been stored and
  then ignored.

### Cosmetic
- Three-digit hex colours expand by nibble repetition (`#abc` ≡ `#aabbcc`)
  rather than ×16, so `#fff` is white instead of `#f0f0f0`. The four-digit
  `#rgba` form drops the alpha nibble instead of misreading it as blue.

### Corrections
- The B030 report claimed dnd5e falls back to `max(cr, 1)` when the caster level
  is not numeric, and that emitting `0` defeated it. Reading the 5.3.3 schema
  while fixing it showed `spell.level` is `nullable: false, initial: 0` — always
  numeric, so no such fallback can fire. Had the suggested fix been applied as
  written ("emit nothing and let the fallback work") the bug would have
  survived. The report is corrected in place.
- `system.identified` was carried as an unresolved candidate. It is declared in
  `IdentifiableTemplate`; the converter was right and the candidate is closed.

### Known limitations
- **B043**: `compatibility.verified` is now `14`, matching the reference module
  and backed by a document-level comparison against it — converting the *Lost
  Mine of Phandelver* export and diffing against the hand-repaired
  `lost-mine-of-phandelver-1.2.0` found no `system` key missing from the
  converter's output, identical CR, HP, AC and size throughout, and the only
  differences in the converter's favour: the repaired module still carries the
  retired `spells.spellN.max` and the unsplit `"humanoid (goblinoid)"` type.
  `coreVersion` deliberately stays at 13, because it is what makes Foundry run
  the NeDB→LevelDB migration the output depends on. Writing LevelDB packs
  directly — which would remove the import-and-migrate step entirely — is still
  open and needs an ADR, being the same dependency question as B031.
- **B031**: compendium enrichment is still unavailable on installs that ship
  LevelDB packs. Reported clearly since 1.0.1, but not readable without the
  dependency ADR-003 rejected — the same blocker as B043.

### Tests
- 47 new schema-conformance cases, 585 total. Every one was checked against a
  reverted tree: 39 of the cases in `test_dnd5e_schema_diff.py` fail without the
  fixes, so they detect the defects rather than describing the new code. The
  full suite passed both before and after these seven fixes, which is exactly
  why the check matters.
- Verified end to end on two real campaigns rather than only in unit tests:
  *Waterdeep Dragon Heist* (210 actors, 1,752 items — 209 creature types parsed,
  42 NPC caster levels recovered, 164 slot overrides, all 55 limited-use items
  carrying a consumption target, no retired field anywhere) and *Lost Mine of
  Phandelver*, compared against the hand-repaired module built from the same
  export.

## v1.0.2

Closes the last two findings of the same class as 1.0.1's, both on the actor
side rather than the item side (B037, B038).

- Tool proficiencies are emitted as the `system.tools` mapping dnd5e reads
  rather than the legacy `traits.toolProf`, which only survived through a
  migration shim. The entry is exactly what that shim writes, so the shape was
  copied from dnd5e rather than guessed.
- Shaped-sheet skills use the same 5.x shape as the standard sheet. They had
  kept the pre-5.x form, so the sheet's flat bonus was dropped for every Shaped
  actor — and the bonus was computed with the wrong sign.
- Skills and tools whose names have no dnd5e key are reported instead of being
  written to a key the schema deletes on load without a warning.
- The schema-conformance tests now cover the actor side as well as items. The
  actor cases drive the emitters through a Shaped-sheet stub rather than
  asserting constants against themselves; reverting the fix fails nine of them.

## v1.0.1

Fixes from the 2026-08-03 output audit (B027–B035, documented in `docs/bugs/`).
Every finding was verified against the dnd5e 5.3.3 source. The 513-test suite was
green throughout, because it asserted the shapes the emitter produced rather than
the ones dnd5e declares — the gap the new schema-conformance tests close.

### Crash
- `createItemClass` no longer raises `KeyError: 'saves'` when a class matches a
  compendium entry. F019 removed those keys from the class item but not the
  statements that deleted them.

### Data loss
- Physical items emit `weight` and `price` as the `{value, units}` and
  `{value, denomination}` objects the schema declares. A bare number does not
  fail loudly — Foundry resets the field — so every converted item had been
  arriving with no weight and no price.
- `attunement` is emitted as a string rather than the 1.5.6 numeric enum.
- Token bars point at `attributes.hp` instead of `attributes.bar1`, which no
  actor schema declares. Unlinked tokens — most converted NPCs — had been
  rendering an empty HP bar and losing their per-token HP overrides.
- Armour emits a dex cap of `null` for light, 2 for medium and 0 for heavy. Every
  armour had been emitting 0, a real cap of +0, so no converted armour granted a
  dex bonus to AC.
- Weapons no longer carry an `armor.value` of 10 and an `hp` block, and equipment
  no longer carries the retired `speed` and `stealth` fields; stealth
  disadvantage is emitted as a property.
- Character XP survives the `"3400/6500"` sheet format; the parsed value had been
  overwritten with 0 unconditionally.
- Spells with a zero high-level bonus no longer gain `" + 0"` upcast scaling from
  a comparison that should have been an assignment.

### Diagnostics
- Compendium pack loading detects the LevelDB directories systems have shipped
  since Foundry v11 and reports that one cause, naming what is lost, instead of
  five unhelpful per-file errors. Reading those packs still is not supported —
  ADR-003's reasons for refusing a native LevelDB dependency are unchanged — so
  compendium enrichment remains unavailable on current installs, but visibly so.

### Tests
- `tests/test_dnd5e_schema_diff.py` asserts emitted `system` dicts against key
  sets read from the dnd5e 5.3.3 templates, including the absence of retired
  fields. This is the mechanical form of the check that B028/B032/B033 each
  needed a reviewer to notice.

## v1.0.0

**Targeting Foundry VTT v13 and dnd5e 5.3.3.** Converted worlds and modules import
with **zero migration** — verified by importing a real export into a real Foundry
and reading the documents back out of storage. See `docs/adr/` for the decision
records and `ROADMAP.md` for the bug/fix log.

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

#### 1.0.0 — acceptance

A real export, converted, imported into Foundry v13 with dnd5e 5.3.3, and then
measured three ways: on the emitted files, on the LevelDB Foundry wrote back, and
by rolling the dice in the live game.

**Zero migrations.** `dnd5e.systemMigrationVersion` never moves, and no document
carries `flags.dnd5e.persistSourceMigration` — dnd5e's migration rewrote nothing,
which is the whole point. 96/96 weapons keep their dice in the **stored**
`damage.base` (the direct negative control for the shim that used to make the
live document read correctly while the stored one held nothing), and 96/96 have
the attack activity the migration never creates.

**The printed stat block is now a test oracle.** Roll20 leaves the author's own
text in each item's description — *"Melee Weapon Attack +4 … Hit: 11 (2d8+2)"*.
`tools/verify_dnd5e.py` parses it and asserts that what dnd5e will roll equals
what the module says. That comparison found four defects a 455-green suite and a
clean schema check had both passed, every one of which produced a document that
loaded without a single error and rolled the wrong number:

- **B023/F023** — not every Roll20 sheet carries `<ability>_mod`. Defaulting it to
  0 left the *document* right, because dnd5e derives the modifier from the score,
  while every internal decision that depends on it went wrong. A Bugbear with STR
  15 and a printed +4 rolled **+8**, and its printed `2d8+2` rolled **2d8+4**.
- **B024/F024** — the to-hit fallback forgot that dnd5e adds proficiency too, so
  a Goblin's printed +5 rolled +7.
- **B025/F025** — the damage extractor picked its own ability while the caller
  kept a different one, so a Goblin's printed `1d6+2` became `1d6−1`.
- **B026/F026** — the proficiency formula divided outside its ceiling and returned
  +1 at CR 0; every CR 0–4 creature has +2.

**Measured, on *TotYP: The Sunless Citadel*** — 30 actors, 357 items: 0 legacy
fields, `_stats.systemVersion` intact on 387/387 documents, 0 activated items
without an activity, 62 dice rolls evaluated in the live game, and **61 to-hit and
damage checks against the printed stat blocks with 0 wrong**.

New: `tools/verify_dnd5e.py` (emitted output, with the oracle) and
`tools/verify_persisted.mjs` (the LevelDB Foundry wrote back). Suite: 455 → 513.

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
