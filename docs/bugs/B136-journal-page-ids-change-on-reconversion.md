# B136: Journal page IDs change on every reconversion

- Severity: Moderate
- Status: Fixed in v1.17.1
- Observed release: R20Converter 1.17.0, commit eae5e7f
- Reported: 13 November 2026, Curse of Strahd 1.4.0 conversion intake D7

## Reproduction

Convert the same export twice. JournalEntry IDs are stable because they derive from the Roll20
handout ID, but every handout's JournalEntryPage IDs differ. Links of the form
`JournalEntry.<id>.JournalEntryPage.<pageId>`, which downstream cross-references and table links
use, break on each reconversion. The Curse of Strahd pipeline remapped them by page position.

## Cause

Generic converter defect. `Handout.genPage` used `Entity.genID()`, a random UUID, for each page.
Captured compendium reference pages were already deterministic because their importer overwrote
the text page ID.

## Resolution

A page ID derives from the handout's source ID and the page type: `<handout id>-text` and
`<handout id>-image`, normalized like every other converter ID. A handout has at most one page of
each type, so the IDs are unique. They do not shift when an avatar is added or removed. The text
page of a captured compendium reference already used this scheme, so its ID is unchanged.

## Verification

`tests/test_document_schema.py` asserts the derivation for text and image pages; the 1.17.0 source
fails it. The compendium-export tests, which link reference pages by ID, pass unchanged.

Two independent conversions of the unmodified Curse of Strahd export produce identical
JournalEntryPage IDs (see the v1.17.1 changelog). Page IDs in modules converted before v1.17.1
change once more on their next reconversion and are stable after that.
