# B055 — items folder numbering ignores non-folder siblings

**Status:** fixed in v1.7.6
**Severity:** high — every "Magic Items" asset path was derived against the wrong directory
**Component:** `src/entities/items.py` → `Items.addToFolder`
**Found:** 7 Aug 2026, auditing the other folder walks for the B053 pattern

## Symptom

Assets for items converted out of a journal folder were looked for in a directory that
does not exist in the export. Nothing failed loudly: the manifest lookup added in 1.7.4
resolves those assets by URL, and before that B049 downloaded them from Roll20 — so the
defect has never been visible in a converted world.

## Cause

`Items.addToFolder` numbers the directories it walks the same way `Journal.addToFolder`
does, and both walk the **same** `journalfolder` array. The exporter numbers *every*
sibling it writes. The items walk advanced its index only for sub-folders, because the
handout and character branches sat behind `elif is_items_folder`:

```python
for item in folder:
    if isinstance(item, dict):
        dirname = "%03d - %s" % (index, item["n"])
        ...
        index += 1
    elif is_items_folder:            # <- gate
        handout = self.findID(item, "handout")
        if handout != None:
            ...
            index += 1
        elif self.findID(item, "character") != None:
            index += 1
```

`is_items_folder` describes the folder currently being walked, not the child. For any
ordinary folder it is false, so handouts, characters and PDFs consumed no index and every
later sub-folder was numbered low. Inside an items folder the gate opened, but there was
still no `pdf` branch — the B053 defect verbatim, which items.py never received.

`--folder-as-items` defaults to `["Magic Items"]` when the flag is not passed
(`main.py`), so this path runs on every conversion.

## Measured

Replaying the walk against the archived exports and comparing with the real zip entries:

| export | zip contains | `items.py` derived |
|---|---|---|
| Storm over Savage Frontier | `journal/074 - Magic Items/` | `029` |
| Wardens of the North S3 | `journal/083 - Magic Items/` | `005` |

Storm has 2 such folders and Wardens 3; all five resolved to the wrong directory. The
seven TotYP modules are unaffected — their Magic Items folder is the first entry of a flat
tree, so an index of 0 happens to be correct.

## Fix

Numbering is now unconditional and matches the exporter; only item *creation* stays gated
on `is_items_folder`, and the `pdf` branch is present:

```python
else:
    handout = self.findID(item, "handout")
    if handout != None:
        if is_items_folder:
            items.append(Item.createItemFromHandout(...))
        index += 1
    elif self.findID(item, "character") != None or self.findID(item, "pdf") != None:
        index += 1
```

An id that resolves to nothing still consumes no index, so the drift is not reintroduced
in the other direction.

## Notes

Third instance of one pattern: **a fallback that succeeds hides the defect it worked
around.** B049 masked B053; the 1.7.4 manifest lookup masked B055. Because every archived
export now carries `export_report.json`, no shipped world needs repairing for this — the
manifest already resolved the assets by URL. The derived path is the fallback for legacy
exports, and it was wrong.

`Folders.addJournalFolder` was audited at the same time and is **not** affected: it
numbers with `index + 1 + len(folders)` for sidebar sort order, not for zip paths. It does
log `Unknown ID in Journal folder` for PDFs, which is how the tree's PDFs were visible all
along. `playlists.py`, `scenes.py` and `tables.py` have no `addToFolder` walk.
