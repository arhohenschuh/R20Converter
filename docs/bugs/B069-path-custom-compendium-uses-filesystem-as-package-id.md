# B069 - Path custom compendium uses filesystem as package ID

**Severity:** High
**Status:** Fixed in v1.14.0
**Found:** 2026-08-20 during frozen LMoP qualification attempt 002

## Defect

`--custom-compendium` accepts either a module ID or a filesystem path. When given the production
Beyond5e extraction path, `loadCustomCompendium()` stored that whole path as each donor's package
identity. The module's real executable UUIDs use `Compendium.beyond5e-2014-compendium...`, so the
assembler could not match Mage Hand even though the donor Actor loaded correctly.

## Fix contract

- Read the donor package ID from the `module.json` beside `packs/`.
- Preserve an ID argument when no manifest exists.
- Use the resolved ID for source entities, merged role databases, UUID indexing, and dependency
  reporting.

## Regression coverage

`tests/test_custom_compendium.py` covers path and ID invocation forms.
`tests/test_module_assembly.py` covers external executable Actor localization.