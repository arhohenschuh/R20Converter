# B088 - Module output drops source Macros

**Severity:** High
**Status:** Fixed in v1.15.2
**Found:** 2026-08-20 during Eberron Setting v1.0.0 source-fidelity reconciliation
**Component:** `src/R20Converter.py`, `src/module.py`, `src/module_assembly.py`, and `src/entities/macros.py`
**Related:** B065, B086

## Defect

World conversion creates and saves `Macros`, but module conversion never instantiates that database.
`Module` has no Macro pack branch and `ModuleAssembler.buildAdventure()` hardcodes `macros: []`.
The conversion therefore succeeds while silently deleting the complete source Macro collection.

The immutable Eberron Setting export contains 87 macros, including six visible to all users and one
token action. Their commands reference source RollTables and rich-text Journal/compendium links.

## Fix contract

- Instantiate Macros in module mode and save nonempty output as a `type: "Macro"` pack.
- Include Macro documents in assembler traversal, folder validation, and the native Adventure.
- Normalize Markdown, Journal, and compendium links inside each command before storage.
- Preserve source IDs, names, command text, visibility-derived ownership, and sort order.
- Do not claim Roll20 chat-template semantics are runtime-qualified merely because documents are
  conserved; runtime sampling remains a separate gate.

## Regression coverage required

A converted Macro must appear in `Adventure.macros`. A Markdown Journal link in a source command
must become the correct local module Journal UUID.

## Resolution

Module conversion now builds `Macros`, `Module` writes a Macro pack, and `ModuleAssembler` includes
the database and Adventure collection. `Macro` command creation uses the common link normalizers.
Focused tests cover both document conservation and command-link closure.