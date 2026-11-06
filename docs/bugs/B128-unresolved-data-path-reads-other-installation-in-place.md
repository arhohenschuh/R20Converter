# B128: Unresolved `--fvtt-data-path` reads another installation's packs in place

- Severity: High
- Status: Fixed in v1.17.0
- Observed release: R20Converter 1.16.4
- Found: 6 November 2026, during B125 validation

## Reproduction

Pass `--fvtt-data-path` with a path that does not resolve, such as one level too deep
(`...\Foundry\Data` instead of `...\Foundry`). The converter logs:

> `'<path>' does not contain Data/systems ... Compendium enrichment will be skipped.`

It then auto-detects the machine's Foundry installation and enriches from that installation's
dnd5e packs. The output depends on whichever system is installed locally, not the path the user
named.

`leveldb_pack.readPack` also opened each pack in place. LevelDB rewrites `CURRENT`, `LOG`,
`MANIFEST-*`, and the numbered journal on open, even for a read. During this investigation, the
validation conversions rewrote those files in five dnd5e 6.0.6 system packs of a live user
installation. A byte copy compared logically with the pristine 6.0.6 release found every
key and value unchanged: 4,411 pairs, with no additions, removals, or value changes.

## Cause

- `R20Converter.__init__` ran auto-detection whenever `fvtt_path` was `None`, including after an
  explicit path failed to resolve.
- `readPack` called `plyvel.DB(path)` directly on the source directory.
- `loadSystemManifest` called `os.path.join(None, ...)` when no path resolved, crashing the
  constructor.

## Resolution

- An explicit `--fvtt-data-path` that does not resolve now skips enrichment, as the warning says.
  Auto-detection runs only when no path is given, which is the GUI default.
- `readPack` copies the pack directory, excluding `LOCK`, to a temporary directory, reads the copy,
  and deletes it. Source packs are never opened, so reading also works while Foundry holds a pack
  open.
- `loadSystemManifest` returns when no data path is available.

Regression coverage includes byte and mtime equality of every pack file across `readPack`
(`tests/test_leveldb_pack.py`), and an unresolved explicit path that stays unresolved while an
absent path still auto-detects (`tests/test_conversion_log.py::TestExplicitDataPath`). Exported
HEAD fails both: `CURRENT` and `LOG` change, and the explicit path resolves to the discovered
installation.

## Operational Note

Earlier pipeline runs with an unresolved explicit path enriched from the auto-detected
installation. They also opened its packs in place. Treat their compendium matches as coming from
that installation, not from the named data.
