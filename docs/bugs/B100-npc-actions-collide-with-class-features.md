# B100 - NPC actions collide with same-name class features

**Severity:** High
**Status:** Fixed in v1.15.9
**Found:** 2026-08-25 while reviewing 90 post-conversion *Multiattack* restorations
**Component:** `src/entities/actors.py` (`Actor.createItemFeat`),
`src/entities/items.py` (`_buildActivities`)
**Related:** B050, B062, B090, B091

## Defect

Every NPC action represented as a feat is offered to the dnd5e **Class Features** compendium by
name. `Multiattack` therefore matches the Hunter level-11 class feature. With
`--no-compendium-overwrite`, the donor template wins and discards both the exact Roll20 NPC action
description and the utility activity the converter had already generated.

Example from immutable *Shattered Obelisk* source:

```text
Sildar makes two Longsword attacks.
```

Accepted and fresh converted output instead store:

```text
At 11th level, you gain one of the following features of your choice.
Volley
Whirlwind Attack
```

All 90 `Multiattack` Items in the accepted 1.4.1 module and the fresh v1.15.8 test conversion have
that same Hunter text. Accepted output has one utility activity on each Item; fresh output has
none. The historical 90-row restoration copied only the accepted activity and therefore did not
repair the wrong content.

### Published fleet scope

A copy-first census selected the latest version of every published converted module with an Actor
pack, extracted each Actor pack to disposable local storage, and opened only that copy. Across 20
modules / 3,281 Actors it measured 1,442 `Multiattack` Items. **979 Items in 14 modules** contain
the exact Hunter collision text. This is systemic but not universal: six modules and every Actor
without a colliding `Multiattack` Item are unaffected.

Affected current modules include *Tomb of Annihilation* (120), *Dungeon of the Mad Mage* (165),
*Out of the Abyss* (124), *Princes of the Apocalypse* (119), *Tyranny of Dragons* (101),
*Shattered Obelisk* (90), *Dragon Heist* (82), and seven smaller modules.

The required post-review census widened the question from exact `Multiattack` spelling to every
normalized NPC feat name present in dnd5e 5.3.3 **Class Features**. Across the same 20 modules it
found 1,968 colliding Items under 20 names. Of those, 1,111 descriptions exactly equal a class-
feature donor: 979 `Multiattack`, 102 `Spellcasting`, 13 `Devil's Sight`, 9 `Evasion`, and eight
smaller groups. The 525 non-`Multiattack` collision Items prove that a one-name exception would
leave the root defect open.

## Cause

`Actor.createItemFeat()` unconditionally calls:

```python
self.findCompendiumItem("Class Features", name)
```

The lookup has no source-surface discriminator. A monster action and a class feature with the same
display name are treated as the same semantic object. This repeats B090's name/type boundary at a
finer level: both documents are feats, but their owning domains differ.

## Required handling

- NPC actions, reactions, legendary/lair actions, and traits must remain source-authored monster
  components. Do not replace them from **Class Features** by name alone.
- Preserve exact Roll20 prose and generate the native activity implied by the source surface.
- A non-roll NPC action such as Multiattack receives one utility activity with action cost 1 and
  `consumption.spellSlot: false`.
- Do not claim one-click execution of constituent attacks unless every referenced action resolves
  uniquely; the utility activity is the faithful baseline.
- Genuine PC/class features retain existing class-feature enrichment.
- Actor-pack and native-Adventure copies must agree.
- Census the retained export/release fleet for other NPC component names colliding with class
  features before release.

## Candidate resolution

`Actor.createItemFeat()` now skips Class Features lookup when the owning Actor is an NPC. The
source Item therefore survives with its generated utility/save/attack activity. `_buildActivities`
explicitly disables spell-slot consumption on non-spell utility activities.

Regression coverage freezes the exact Sildar source sentence, rejects Hunter text, requires one
action-cost utility with no spell-slot consumption, and proves PC lookup remains available.
The focused ownership-boundary suite passes 2/2 and the neighboring asset/compendium suite passes
62/62. The complete candidate suite passes 947/947 before independent review.

Independent Opus QA passed all 6 targets with zero findings and rejected all 7 negative controls.
It approved the `isNPC()` boundary as safer than a second source-surface discriminator because all
four reachable call sites already consume only NPC repeating sections, including shaped aliases.
The sealed 19-file packet remained byte-identical at lock SHA-256
`AF3C834F501F259A0A474D54A0098AB3561C5ECCC3370B82EF051F8C772C9F98`.

Post-review census: 20/20 modules, 3,281 Actors, 9,828 embedded feats, 1,968 colliding Items,
1,111 exact donor descriptions, and 20 colliding names. The report is 29,875 bytes with SHA-256
`87D3E72E3B7AB323D58553D830165F584DC15743E4185BCA9991BD13F902F6B6`; removing the normalized
`Multiattack` donor changed the measured population from 1,968 to 525 and confirmed the RED
control. The final combined B097/B100 release suite passes 963/963.
