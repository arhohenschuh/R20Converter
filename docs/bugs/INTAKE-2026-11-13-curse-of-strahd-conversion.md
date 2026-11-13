# Intake: Curse of Strahd 1.4.0 conversion defects (2026-11-13)

- Reporter: Conversion Pipeline-14 (Curse of Strahd 1.4.0 full redo, run `D:\Automation_Local\Work\DnD5e\cos\v140`)
- Observed release: R20Converter 1.17.0, commit `eae5e7f`, `--dnd5e-version 6.x`, `--srd-edition 2014`
- Input: *Curse of Strahd* R20Exporter 1.5.7 campaign export (defects D1-D3 are also present in the 1.0.0 export)
- Status: **triaged 2026-11-13** by the converter owner; every item is dispositioned below. The
  original text is kept as reported.

| Intake | Disposition |
| --- | --- |
| D1 ellipse | Duplicate of [B130](B130-flat-jumpgate-ellipse-outside-walls-aborts-conversion.md), fixed in v1.17.1 |
| D1 rectangle | Did not abort; exposed [B137](B137-jumpgate-rectangle-wall-becomes-one-diagonal.md) (rectangle Walls became diagonals), fixed in v1.17.1 |
| D2 | [B131](B131-numeric-string-font-size-aborts-conversion.md), fixed in v1.17.1 |
| D3 | [B132](B132-token-for-deleted-character-aborts-module-assembly.md), fixed in v1.17.1 (no name relink) |
| D4 | [B133](B133-npc-without-source-spellcasting-has-no-slots.md), not a converter defect: the source sheet has no spellcasting |
| D5 | [B134](B134-printed-npc-slot-spread-ignored.md), fixed in v1.17.1 |
| D6 | [B135](B135-equivalent-compendium-link-forms-resolve-differently.md), fixed in v1.17.1; the stray Items are B071 donor internalization from links *without* a slash |
| D7 | [B136](B136-journal-page-ids-change-on-reconversion.md), fixed in v1.17.1 |

- Previous status: **unnumbered intake**. The register owner assigns B-numbers (next free per README: B131) and moves each item into its own `Bnnn-*.md` file.
- Evidence: console logs `Reports\Logs\convert-c1-failed-degenerate-path.console.log`, `convert-c2-failed-font-size.console.log`, `convert-c3-failed-guard-link.console.log`; workaround shim `Tools\make-path-shim.mjs` / `Reports\path-shim-003.json`; output repairs `Tools\fix-cos-actors.mjs` and `Tools\fix-aliases.mjs` (all in the run folder).

> **Note on upstream issues.** This fork has GitHub issues disabled, so `gh issue create` in this checkout went to the public upstream `kakaroto/R20Converter` as #98-#103 under the owner's account. The owner decides whether to keep or close them; this file is the fork-side record.

> **Overlap with B130.** The pending v1.17.1 B130 fix (flat/point Jumpgate ellipses skipped on every layer) appears to cover the D1 ellipse (points `[[0,0],[0,-0.51]]`). The zero-width **rectangle** `-OmocrgJSUwA3kBjW6kB` in D1 is not covered by B130 and is unverified.

### D1: Conversion aborts on a zero-size barrier ellipse ("Path ... is a degenerate ellipse")

Upstream copy: kakaroto/R20Converter#98 (filed under the owner's account; see note above).

#### Summary
R20Converter v1.17.0 (`eae5e7f`) aborts the whole conversion when a page contains a zero-size ellipse on the walls layer.

#### Input
Curse of Strahd, R20Exporter 1.5.7 export (also present in the 1.0.0 export), page *Tsolenka Pass*, path `-OmuNHy9W4nPWaAJ0obb`:

```json
{"path": null, "points": [[0,0],[0,-0.51]], "shape": "eli", "layer": "walls", "barrierType": "transparent",
 "width": 0, "height": 0, "x": 1830.13, "y": 1902.11, "stroke": "#00ffff", "stroke_width": 5}
```

A stray click in Roll20: it has no area and no gameplay meaning.

#### Result
```
Path '-OmuNHy9W4nPWaAJ0obb' is a degenerate ellipse
Error converting campaign with R20Converter v1.17.0
```
`src/entities/scenes.py` raises `ValueError` (around lines 1292/1295) when `w <= 0 or h <= 0`.

#### Expected
Skip zero-area barrier shapes with a warning (they cannot produce walls). One unusable drawing should not abort a 50-page campaign.

#### Related, unverified
The same export has a zero-width walls-layer rectangle on *Ravenloft Map 7-10* (`-OmocrgJSUwA3kBjW6kB`, `shape: "rec"`, width/height 0, point span 0 x 2.22). It was removed together with the ellipse and was not tested on its own.

#### Workaround used
A conversion-only copy of the export with these two path objects removed from `campaign.json` and their `pages/*/page.json`.

### D2: TypeError when a text object stores font_size as a string ("can't multiply sequence by non-int of type 'float'")

Upstream copy: kakaroto/R20Converter#99 (filed under the owner's account; see note above).

#### Summary
R20Converter v1.17.0 (`eae5e7f`) crashes on Roll20 text objects whose `font_size` is a numeric **string**.

#### Input
Curse of Strahd export (both 1.0.0 and 1.5.7): 13 text objects on 6 pages (Ravenloft Map 3, Ravenloft Map 12, Death House - Dungeon, Argynvostholt (Ground & Second Floor), Token Page), e.g. page *Ravenloft Map 3*, text `-OoCmQphDPe-5Apod1lC`:

```json
{"type": "text", "font_size": "12", "font_family": "...", "text": "GM Note:\n..."}
```
The other 37 text objects in the campaign use a number (`"font_size": 12`).

#### Result
```
  File "src\entities\scenes.py", line 601, in __init__
    drawing["fontSize"] = text["font_size"] * grid_multiplier
TypeError: can't multiply sequence by non-int of type 'float'
```
(`scenes.py` line 582 and 1411 read the same field.)

#### Expected
Coerce `font_size` with `float(...)` (falling back to a default with a warning when it is not numeric).

#### Workaround used
A conversion-only copy of the export with the 13 string values converted to numbers.

### D3: Conversion aborts on a token whose Roll20 character was deleted ("broken token actor link")

Upstream copy: kakaroto/R20Converter#100 (filed under the owner's account; see note above).

#### Summary
R20Converter v1.17.0 (`eae5e7f`) aborts at module assembly when a placed token `represents` a character that no longer exists in the campaign.

#### Input
Curse of Strahd export (1.0.0 and 1.5.7), page *Town of Vallaki*, token `-KmADi3x3v52UxF7FxaV` (name "Guard", GM layer) with `represents: "-KgKKC8RJ3IY34mnYJTR"`; no character with that id exists (deleted in Roll20). A character named "Guard" (`-NQWMoDPWUQxXROgLOn5`) exists.

#### Result
```
broken token actor link NGVjOTU0NmM3ODMy
Error converting campaign with R20Converter v1.17.0
```
`src/module_assembly.py` around line 575 raises `ValueError` after the whole campaign has been converted.

#### Expected
Detect it while creating the token: either drop the actor link (keep the token as an unlinked/decorative token) or, optionally, relink by exact unique name, and warn. Failing at the very end of a long conversion over one GM-layer token is costly.

#### Workaround used
A conversion-only copy of the export with the token's `represents` set to the existing Guard (the same repair as an earlier manual fix of this module).

### D4: NPC spellcaster converted without spellcasting ability or spell slots (Strahd von Zarovich)

Upstream copy: kakaroto/R20Converter#101 (filed under the owner's account; see note above).

#### Summary
With R20Converter v1.17.0 (`eae5e7f`, `--dnd5e-version 6.x`, `--srd-edition 2014`, custom compendium Beyond5e 1.6.72 additive), the Roll20 NPC *Strahd von Zarovich* (Curse of Strahd, ogl5e sheet, a 9th-level Intelligence spellcaster with 4/3/3/3/1 slots) converts with:

- `system.attributes.spellcasting = ""`
- `system.attributes.spell.level = 0`
- every `system.spells.spellN = { value: 0, override: null }`

so the sheet cannot cast any leveled spell. His prepared spell items are present.

#### Expected
Spellcasting ability, caster level and slot pools from the Roll20 sheet (ogl5e `npcspellcastingflag`, `spellcasting_ability`, `caster_level`, `lvlN_slots_total`), i.e. `int`, 9, 4/3/3/3/1.

#### History
An older conversion (R20Converter 1.7.7) showed a related state split: positive slot overrides but `value` 0 on 25 NPCs. 1.17.0 now loses the values entirely for this NPC.

#### Workaround used
Post-conversion repair of the Actor (pack and Adventure): spell level 9, `int`, slots 4/3/3/3/1 (value + override).

### D5: Half-caster NPC gets a full-caster slot table (Sir Godfrey Gwilym, 16th-level paladin)

Upstream copy: kakaroto/R20Converter#102 (filed under the owner's account; see note above).

#### Summary
R20Converter v1.17.0 (`eae5e7f`) converts the Roll20 NPC *Sir Godfrey Gwilym* (Curse of Strahd; his Spellcasting trait: 16th-level **paladin**, slots 1st 4, 2nd 3, 3rd 3, 4th 2) with `system.attributes.spell.level = 16` and no slot overrides. dnd5e then derives a **full-caster** level-16 table:

`spell1..spell8 = 4/3/3/3/2/1/1/1` (only `value` set, `override` null)

instead of 4/3/3/2 and nothing above 4th level.

#### Expected
For NPCs whose Roll20 sheet / trait names a half caster (paladin, ranger) or pact caster, carry the sheet's slot totals as explicit overrides (`lvlN_slots_total`), and pin unused levels to 0, instead of relying on dnd5e's full-caster derivation from `spell.level`.

#### Workaround used
Post-conversion repair: levels 1-4 pinned to 4/3/3/2, levels 5-9 pinned to 0.

### D6: Compendium links with a trailing slash ("Spells:Light/") become stray world Items instead of links

Upstream copy: kakaroto/R20Converter#103 (filed under the owner's account; see note above).

#### Summary
R20Converter v1.17.0 (`eae5e7f`) resolves Roll20 Compendium links whose target ends in a slash, e.g.

```html
<a href="https://app.roll20.net/compendium/dnd5e/Spells:Light/">Light</a>
<a href="https://app.roll20.net/compendium/dnd5e/Spells:Darkvision/">Darkvision</a>
```

(Curse of Strahd export: 4 Light and 6 Darkvision occurrences) by creating **world spell Items** `Light14IIIIIIIII` / `Darkvision14IIII` in the module's Items pack and linking to them, while the same targets without the slash are not handled this way. The log also shows:

```
Could not find compendium item of type 'Spells' and name 'Darkvision/'
Could not find compendium item of type 'Spells' and name 'Bless/'
```

#### Expected
Normalize the target (strip the trailing slash, as well as `?expansion=...` query strings and markup inside the URL path such as `&lt;em&gt;`) before lookup, and resolve like any other spell link. Do not add top-level Items for link targets.

#### Workaround used
Post-conversion: the two links retargeted to the localized spell journals and the two Items deleted.

### D7: Journal page IDs are not stable across converter versions (observation)

Converting the same Curse of Strahd source with 1.17.0 kept JournalEntry IDs stable against the earlier conversion (published module 1.3.1), but JournalEntryPage IDs changed. Downstream links that target `JournalEntry.<id>.JournalEntryPage.<pageId>` (carried-over cross-references, table links) therefore break on reconversion and had to be remapped by page position (`Tools\carry-table-links.mjs`, `Tools\repair-links.mjs`). Expected: derive page IDs deterministically from the Roll20 handout ID plus page index, as is already done for entries. Severity: Low/Medium (reconversion cost only).