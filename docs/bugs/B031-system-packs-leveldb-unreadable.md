# B031: Compendium pack loading reads NeDB `.db` files — modern dnd5e ships LevelDB directories

- **Status**: Fixed in 1.3.0 (F031b). Reported with its real cause in 1.0.1 (F031); fully fixed once ADR-009 brought in the LevelDB dependency ADR-003 had rejected
- **Severity**: Major (all compendium enrichment silently disabled on current installs)
- **Found**: 2026-08-03 audit
- **Component**: `src/R20Converter.py` (`loadDnD5ePacks`, `loadSystemPacks`), `src/leveldb_pack.py`

## Resolution (1.3.0)

ADR-009 added `plyvel` to write LevelDB module packs. Reading them is the same
dependency, so the blocker recorded here disappeared with it.

- `loadDnD5ePacks` / `loadSystemPacks` prefer the LevelDB directory and fall
  back to a NeDB `.db` file where one still exists.
- The pack reader works the collection out from the key prefixes rather than
  being told it: a system pack is named for its content, not its document type
  (`spells24`, `actors24`), so the name says nothing useful.
- The 2014 SRD packs are used, not the `*24` ones. A Roll20 campaign's content
  predates the 2024 rules, and matching a 2014 sheet against a 2024 document of
  the same name would swap in a different edition of the spell.
- The warning now only fires when LevelDB support is genuinely missing (a
  source install without `plyvel`), and names the import error.

Measured on the reporter's dnd5e 5.3.3 install: 1,851 documents read from the
five packs in under a second, and a *Sunless Citadel* conversion matched 114 of
357 items (68 spells, 34 weapons, 12 feats), which arrive with system icons and
their compendium activities rather than Roll20 artwork.

## Defect

```python
path = os.path.join(self.fvtt_path, "Data", "systems", "dnd5e", "packs", "%s.db" % file)
db.load(path)
```

Since dnd5e 3.0 (Foundry v11), system packs are **LevelDB directories**
(`packs/items/000010.ldb`, `CURRENT`, `MANIFEST-…`), not newline-delimited-JSON
`.db` files. Verified against a live dnd5e 5.x install
(`Data/systems/dnd5e/packs/items` is a LevelDB directory; no `*.db` files exist).
`db.load()` therefore throws for every pack, each failure is logged (ADR-001), and
`self.packs` stays empty.

## Impact

`hasSystemPacks()` is False on every current install, so all downstream
enrichment silently degrades:

- `findCompendiumItem` / `findCompendiumActor` never match → no SRD images,
  no item/spell/class-feature enrichment, no weapon `type.value` from the
  compendium (`_compendiumWeaponType` fallback path).
- Roll20 compendium links in journals/bios are left as dead roll20.net anchors
  (`Entity._foundCompendium` warning path).
- Non-dnd5e systems: `loadSystemPacks` fails the same way for any system
  updated to LevelDB packs.

This also *masks* **B027** — the class-compendium crash only fires once packs
load again.

## Suggested fix

ADR-003 already introduces the Foundry CLI / LevelDB tooling for *writing*
packs; reading needs the same treatment. Options, in order of preference:

1. Read packs through `plutodb`/`leveldb` bindings (pure-python `plyvel` or the
   `fvtt-cli` extract step ADR-003 uses) into the existing `DatabaseFile` shape.
2. Support the dnd5e source-repo JSON packs (`packs/<name>/*.json` in the
   repository layout) as an alternative `--dnd5e-src-path`.
3. At minimum: detect the directory case and emit one clear warning naming the
   actual cause ("dnd5e ships LevelDB packs; this build cannot read them")
   instead of five generic load failures.
