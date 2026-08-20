# B075 - Missing compendium link becomes invalid Item UUID

**Severity:** Minor
**Status:** Fixed in v1.14.0
**Found:** 2026-08-20 during frozen LMoP qualification

When a Roll20 compendium URL could not be resolved to an installed Item, module conversion emitted
`@UUID[Item.<visible name>]`. Names such as `Ability Scores`, `Combat`, and `Resting` are not
16-character world Item IDs, so Gate G16 reported 72 dangling internal links.

Resolved entries still emit typed compendium UUIDs. Unresolved module entries now keep their
visible label and log the missing compendium source, matching the fail-readable behavior used for
absent Roll20 Journal targets. `tests/test_document_schema.py` covers the exact Rules link shape.