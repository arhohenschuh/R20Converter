# Intake: Waterdeep: Dragon Heist 1.3.0 conversion observations (2026-11-13)

- Reporter: Conversion Pipeline-14 (Waterdeep: Dragon Heist 1.3.0 full redo, run `D:\Automation_Local\Work\DnD5e\dragon-heist\v130`)
- Observed release: R20Converter 1.17.1 (archive SHA-256 `F8F6A9E8...A97B`, commit `ec39f13`), `--dnd5e-version 6.x`, `--srd-edition 2014`,
  Beyond5e 2014 compendium 1.6.72 as donor source
- Input: *Waterdeep - Dragon Heist* R20Exporter 1.3.0 campaign export + *Dragon Heist* compendium export 1.5.2
- Status: **triaged 2026-11-13** by the converter owner. The original text is kept as reported.

| Intake | Disposition |
| --- | --- |
| E1 | [B138](B138-foreign-flag-asset-paths-abort-module-assembly.md), fixed in v1.17.2. Converter defect, not Beyond5e: Beyond5e documents the Tokenizer paths as an unrendered re-edit recipe |
| E2 | [B139](B139-categoryless-compendium-links-never-resolved.md), fixed in v1.17.2. The cause is the category-less URL form, not the fragment; an apostrophe parsing flaw was found and fixed with it |
| E2 empty-target links | Not a converter defect: `compendium/dnd5e/` with a blank or comma label is a Roll20 source artefact and stays unchanged |
| E2 `compendium/monstermanual/...` | Not resolved by design: the converter resolves only `dnd5e` entries, through its Spells and Items lookups |

- Previous status: **unnumbered intake**. The register owner assigns B-numbers. The run worked around both items in its own output; nothing in
  this file requires a converter change to finish the 1.3.0 release.

| Intake | Summary | Run workaround |
| --- | --- | --- |
| E1 | Conversion aborts on foreign-module asset paths inside donor Actor **flags** (`flags.tokenizer-2.layerStack[].src`) | Added `tokenizer-2/img` (153 files) to ConverterData; stripped the flags and the 13 internalized images afterwards |
| E2 | Roll20 Compendium links with a `#fragment` (`#content`, `#h-...`) stay Roll20 links, although the target spell was internalized as a module Item | Post-conversion UUID map (`Tools\make-link-map.mjs`, `Tools\repair-links.mjs`) |

## E1: "could not internalize module asset modules/tokenizer-2/img/..." aborts the conversion

### Summary
R20Converter 1.17.1 aborts the whole conversion when a Beyond5e donor Actor carries Tokenizer layer data whose image paths point at
another module (`modules/tokenizer-2/img/...`) that is not present in the converter data root.

### Evidence
- `Reports\Logs\convert-c1.console.log`: `ValueError: could not internalize module asset modules/tokenizer-2/img/dark-texture.webp`
- `Reports\Logs\convert-c2.console.log` (after adding that one file): `... modules/tokenizer-2/img/thegreatnacho/theGreatNacho-16.webp`
- `Reports\converter-data-addendum-001.json`: the run then supplied the whole `tokenizer-2/img` folder (153 files) from the owner's Foundry; c3 converted.
- Affected donors: 20 spell-summon / familiar Actors (Bat, Camel, Cat, Crab, Elk, Frog, Hawk, Lizard, ...). The only references to the 13
  internalized images were those `flags.tokenizer-2.layerStack` entries (`Reports\strip-tokenizer-apply-001.json`).

### Expected
Asset paths inside `flags` of other modules are not displayed by Foundry. They should not abort the conversion: either drop the foreign flag
namespace from donor documents, or leave such paths untouched with a warning instead of raising.

## E2: fragment-bearing Roll20 Compendium links are not resolved

### Summary
After conversion, 40 links to 23 targets still pointed at `roll20.net/compendium/...`. Every remaining 2014 spell link carries a fragment,
e.g. `https://roll20.net/compendium/dnd5e/Detect%20Magic#content`, `.../Tasha's%20Hideous%20Laughter#h-Tasha's%20Hideous%20Laughter`,
`.../Antipathy%20(Sympathy)#content`. For 11 of them the converter had internalized the spell as a module Item (B071), so a local target
existed (`Compendium.waterdeep-dragon-heist.items.Item.DetectMagic14III`, ...). The fragment is the common factor of the unresolved
spell links; it is not verified that it is the only cause.

Also unresolved: `app.roll20.net/compendium/monstermanual/Monsters:Poltergeist#content`, `.../Monsters:Psychic%20Gray%20Ooze#content`,
`.../monstermanual/swarm of quippers#content` (no local target; expected to stay links), and seven bare `roll20.net/compendium/dnd5e/` links whose
labels are whitespace or a comma (Roll20 source artefacts; could be unwrapped to their text).

### Evidence
- `Inputs\Policies\link-map-001.json` (every remaining key, its labels and the local target the run chose)
- `Reports\links-dry-001.json` / `links-apply-001.json` (40 links; 12 blank labels, 2 punctuation labels unwrapped)

### Expected
Resolve compendium links after dropping the URL fragment, the same way B135 normalizes trailing slashes and `app.`/`www.` hosts.
