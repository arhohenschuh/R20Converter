# B058 — legacy-DL doors convert to plain walls

**Status:** fixed in v1.10.0
**Severity:** high — every door on a legacy dynamic-lighting page; rooms become sealed boxes
**Component:** `src/entities/scenes.py` → `Scene.genEntities`, the `path` branch (door colour selection)
**Found:** 14 Aug 2026, from a converted *Waterdeep: Dragon Heist* villa in a live world with zero doors

## Symptom

A converted scene has **no door walls at all** — `door: 0` on every segment. The walls are
present and correctly positioned, sight/light/sound are right, but there is nothing to
open: every doorway is a solid, impassable wall. A GM can only cross by deleting walls.

It does not look like a converter defect from inside Foundry, because other scenes in the
same world *do* have working doors. Whether a page keeps its doors depends on which Roll20
dynamic-lighting generation drew it.

## Cause

Roll20 has two different ways of expressing a door, and only one of them survives.

**Jumpgate / UDL** stores a door as an object in the page's `doors` collection, with
`isOpen` / `isLocked` / `isSecret`. `Scene.genEntities` handles these in its `door or window`
branch and emits them correctly, hardcoding `move: 20` and mapping the states.

**Legacy DL** has no door object. A door is an ordinary path on the walls layer, drawn in a
**different stroke colour** — the GM's own convention, and the only thing distinguishing a
door from a wall. The converter reads that convention here:

```python
door_color = self.getArgument("door_color", None)
secret_door_colors = [self.getArgument("secret_door_color", None)]
if self.getArgument("auto_doors", False) or self.getArgument("interactive", False):
    ...
    door_color = wall_colors_sorted[1][0]
```

```python
door_type = 1 if path["stroke"] == door_color else (2 if path["stroke"] in secret_door_colors else 0)
```

`door_color` defaults to **`None`** and is only populated by `--door-color`,
`--secret-door-color`, `--auto-doors` or `--interactive`. With none of those passed, no
stroke can ever equal it, so `door_type` evaluates to `0` for **every path on the page** and
all door information is discarded silently.

### The GUI and the CLI disagree on the default

This is the operative cause. The GUI ships door detection **enabled**
(`client/src/components/AdvancedOptions.vue`, *"Automatically detect doors from walls"*):

```js
autoDoors: true,
```

while `main.py` declares the same option as opt-in:

```python
parser.add_argument("--auto-doors", action="store_true", help="Automatically detect doors and set them as such.")
```

From identical input, a GUI conversion therefore keeps its doors and a CLI conversion loses
them. The pipeline drives `R20Converter-cli.exe`, which is why every shipped module is
affected. The capability is not missing — the default flips depending on how the converter is
invoked, and the losing side is silent.

None of the shipped conversions passed those flags. *Storm over Savage Frontier*, for
example, was converted with:

```text
--dedup-assets --enable-token-vision --dont-export-actor-items
--custom-compendium … --custom-compendium-mode replace --srd-edition 2014
--npc-source "Roll 20" --fvtt-data-path …
```

## Evidence

*Waterdeep: Dragon Heist*, two pages, measured from the export:

| page | paths | `doors[]` | `barrierType` | strokes | segments |
|---|---:|---:|---|---|---|
| Cassalanter Villa `-LImXzYolryEh7OQOQ2p` | 191 | **0** | `wall` ×191 | `#0000ff` 124, `#ff9900` 67 | 317 = 247 + **70** |
| Temple of Asmodeus `-LImXzijUt8IEesGoQ6O` | 111 | **0** | `wall` ×111 | `#0000ff` 90, `#ff9900` 21 | 533 = 448 + **85** |

The minority colour is doors, not decoration. Segment geometry separates the two cleanly —
on Cassalanter Villa **every one of the 67 orange paths is ≤ 2.3 grid squares** (median 0.50,
99 % ≤ 2 squares) while blue runs reach 40 squares. The campaign owner confirmed the same
convention visually in Roll20: blue = wall, orange = door.

Contrast a Jumpgate page, *Tomb of Annihilation* → Hrakhamar `-Nz8rzupGT-G-ObXEu72`:

| paths | `doors[]` | `barrierType` | strokes |
|---|---:|---|---|
| 43 | **10** (1 locked) | `wall` 28, `transparent` 15 | `#0000ff` 28, `#00ffff` 15 |

Its doors convert correctly, which is exactly why the defect looks intermittent.

## Measured impact

Sweep of one `campaign.json` per archived campaign (`legacy-door-sweep.cjs`). A page counts
as legacy-encoded when it has walls, **no** `doors[]` objects, every `barrierType` is `wall`,
and more than one stroke colour is present. "door segments" is the count in the
non-dominant colours — candidates, since only the two pages above are individually confirmed.

| | |
|---|---:|
| pages total | 527 |
| pages with walls | 321 |
| pages using the legacy door encoding | **157** (49 % of walled pages) |
| wall segments total | 187,013 |
| segments in non-dominant colours (door candidates) | **3,887** |

| campaign | walled | legacy | door segments |
|---|---:|---:|---:|
| `waterdeep-dragon-heist` | 41 | 40 | **1,261** |
| `princes-of-the-apocalypse` | 20 | 17 | 546 |
| `dragons-of-icespire-peak` | 28 | 21 | 304 |
| `ghosts-of-saltmarsh` | 23 | 18 | 259 |
| `tftyp-dead-in-thay` | 9 | 9 | 255 |
| `tftyp-against-the-giants` | 7 | 7 | 235 |
| `storm-kings-thunder` | 26 | 20 | 218 |
| `the-shattered-obelisk` | 33 | 1 | 182 |
| `tftyp-the-hidden-shrine-of-tamoachan` | 3 | 3 | 180 |
| `tftyp-the-sunless-citadel` | 3 | 3 | 116 |
| `out-of-the-abyss` | 18 | 9 | 91 |
| `tftyp-tomb-of-horrors` | 1 | 1 | 83 |
| `tftyp-the-forge-of-fury` | 5 | 4 | 76 |
| `tftyp-white-plume-mountain` | 1 | 1 | 59 |
| `dragoncoast-danger` | 4 | 2 | 22 |

*Waterdeep: Dragon Heist* is almost entirely legacy — 40 of its 41 walled pages.

## Why every existing gate passed

Identical to B057. Every wall exists, at the right coordinates, with correct
sight/light/sound; only its **type** is wrong. Gate A and Gate B never read `door`, and a
scene screenshot looks correct because a closed door and a wall render the same. The defect
is visible only by trying to open a door, or by counting `door` values against the source.

## Suggested fix

The information needed is on the page, so this should not require a flag:

1. **Align the CLI default with the GUI.** Make door detection the default and add
   `--no-auto-doors` to opt out. This is a one-line change that fixes every future CLI
   conversion; everything below is refinement.
2. **Scope the detection to pages that need it** — a page with walls, an empty `doors[]`,
   every `barrierType == "wall"`, and more than one stroke colour is legacy-encoded. Run the
   colour analysis there and skip it on Jumpgate/UDL pages, which already carry real doors.
3. **Warn when detection is off.** If a page looks legacy-encoded and no door colour is set,
   log a per-page warning naming the candidate colour and its segment count, so a silent
   total loss becomes a visible decision. A silent `door_type = 0` for an entire page is the
   actual harm here.
4. Keep `--door-color` / `--secret-door-color` as the explicit override, and keep the
   existing `barrierType != "wall"` guard, which correctly stops `oneWay` and `transparent`
   barriers from being classified as doors.
5. **Secret doors are unrecoverable when the GM used a single door colour.** Do not guess:
   emit plain doors and say so in the log.

A gate is also worth adding: for every converted scene, assert that the number of emitted
door walls matches the source's door objects plus door-coloured segments.

## Recovering already-converted worlds

The door positions are still in the export, so existing worlds can be repaired without
re-converting. Method used on *Storm over Savage Frontier* (scene `ODYyZjFmOTllNTgy`,
Temple of Asmodeus):

- Rebuild the source segments, fit scale/offset from the two bounding boxes, and match each
  segment to a live wall by nearest endpoint pair.
- Result **533/533 matched, 1.55 px mean and 3.74 px worst error** on a 70 px grid. The
  alternative origin convention was rejected at 603 px mean error and serves as the negative
  control. Roll20's path `left`/`top` is the shape **centre**.
- The 85 matched walls were set to `door: 1`, `ds: 0`; movement, sight, light, sound and all
  coordinates were verified unchanged after a client reload.

Tool: `map-doors.cjs` (read-only planner; emits per-wall match error before anything writes).

## Notes

Same family as B048, B056 and B057: Roll20 changed where a meaning lives, and the converter
kept reading the old location. Here the twist is that the old location is a *convention*
rather than a field, so the converter needs the GM's colour key — and defaults to discarding
it.

**A re-export cannot be assumed to recover this.** Roll20's UDL auto-conversion can drop the
legacy layer outright: the same Cassalanter Villa page in a newer *Storm over Savage
Frontier* export carries the identical page id and identical `zorder` (398) and `graphics`
(184) counts, but `paths: 0`, with `udl_auto_converted` set. The older Dragon Heist export is
the only surviving copy of those wall and door positions. Archived exports should be treated
as irreplaceable for any campaign Roll20 has since migrated.

## Fix (v1.10.0)

`Scene.shouldClassifyDoorsByColour` derives the encoding from the page instead of requiring a
flag, because neither "always classify" nor "never classify" is correct:

| Page | Behaviour |
|---|---|
| carries `doors` objects | trust them; **never** colour-classify |
| no `doors`, more than one wall colour | legacy encoding — classify by colour |
| no `doors`, a single colour | nothing to infer |

The first rule is why simply defaulting `--auto-doors` on would have been wrong. *Dungeon of
the Mad Mage*'s Crystal Labyrinth carries **55 real door objects and five wall colours**;
blanket classification would have turned 39 green and 1 black segments into secret doors.
One module can hold both encodings — that same module's Twisted Caverns has no door objects
and 12 orange segments that genuinely are doors, and *Curse of Strahd* and *Lost Mine of
Phandelver* are mixed the same way.

`--no-auto-doors` disables inference; an explicit `--door-color` still wins; `--auto-doors`
is now a no-op kept for compatibility. Tests: `tests/test_legacy_doors.py`, using the
measured shapes of Cassalanter Villa, Temple of Asmodeus, Hrakhamar, Sargauth, Crystal
Labyrinth and Twisted Caverns. Negative-controlled: reverting to the flag-gated derivation
turns 8 of them red.

> ⚠ **Two independent counts of the affected population disagree and are not yet
> reconciled.** This record measures **157 of 321 walled pages (49%)** and 3,887
> non-dominant segments. A second pass over the same archived exports — counting a page as
> affected when its `barrierType: "wall"` paths carry more than one distinct `stroke`, and
> excluding *Storm over Savage Frontier* — measures **272 of 392 walled pages (69%)** and
> 6,571 minority segments. The gap is in the criteria, not the fix, and the fix is per-page
> so it is unaffected either way. Reconcile before either number is quoted anywhere else.
>
> Where the two agree: **11 of 22 campaigns carry no door objects at all** — Dragon Heist
> (40 of 41 walled pages), Storm King's Thunder (19 of 25), Dragons of Icespire Peak,
> Ghosts of Saltmarsh, Princes of the Apocalypse, Out of the Abyss, Dragoncoast and all
> seven TotYP modules. `#ff9900` is the door colour in every campaign checked.
