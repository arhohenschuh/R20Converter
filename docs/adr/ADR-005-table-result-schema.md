# ADR-005: Emit the Foundry v13 `TableResult` schema

* Status: Accepted
* Date: 2026-07-25
* Supersedes: none
* Related: [ADR-002](ADR-002-target-foundry-v13.md)

## Context

`src/entities/tables.py` emitted the Foundry v9 shape for rollable table
results:

```json
{ "type": 2, "collection": "r20-module.cards", "resultId": "abc", "text": "Ace" }
```

Three separate breaking changes have landed since then, and they did not all
arrive in the same release, so they need to be treated individually:

1. **`type` became a string in v12.** `CONST.TABLE_RESULT_TYPES` changed from
   `{TEXT: 0, ENTITY: 1, COMPENDIUM: 2}` to string values. `TableResult.migrateData()`
   still coerces a numeric `type` (`0` → `"text"`, anything else → `"document"`),
   so the old values are not a hard validation error — but they are deprecated.
2. **The compendium result type was removed in v13.** `"pack"` is folded into
   `"document"`, and `CONST.TABLE_RESULT_TYPES.COMPENDIUM` is a deprecated
   accessor that simply returns `"document"`. v13 therefore has exactly two
   valid values: `"text"` and `"document"`.
3. **`documentCollection` + `documentId` were replaced by `documentUuid` in v13.**
   The pair survives only as deprecated shim properties (`since: 13, until: 15`).
   Likewise `text` was split into `name` (for document results) and
   `description` (for plain-text results), also deprecated `since: 13`.

Note that the v9 field names this project actually wrote (`collection`,
`resultId`) predate even the v10 `documentCollection`/`documentId` pair, so
there is no reason to target the intermediate names.

## Decision

Emit the canonical v13 schema directly, skipping the deprecated intermediates:

* `type` is `"text"` or `"document"` (`Table.RESULT_TYPE_TEXT` /
  `Table.RESULT_TYPE_DOCUMENT`). `RESULT_TYPE_ENTITY` and
  `RESULT_TYPE_COMPENDIUM` are gone — there is no longer a distinction between
  a world document result and a compendium document result.
* A single `documentUuid` replaces `collection` + `resultId`, built by the new
  `Table.resultUuid()` helper. World documents become `"<Collection>.<id>"`
  (e.g. `Item.abc`); compendium documents become
  `"Compendium.<packageId>.<packName>.<DocumentName>.<id>"`.
* Both `name` and `description` are populated with the result label. Text
  results read `description`; document results read `name`. Writing both keeps
  a single code path and costs nothing.
* `documentUuid` is `null` for text results rather than the old empty string,
  matching the field's `nullable: true` declaration.

## Consequences

* Rollable tables and card decks import into v13 without deprecation warnings.
* Output is **not** backwards compatible with v9–v11, consistent with ADR-002.
* `Table.resultUuid()` hard-codes `Item` as the document type segment because
  every compendium-backed table result this converter produces is a card item.
  If tables ever reference actors or journals, the caller must pass the document
  type through.
* Covered by `tests/test_document_schema.py`.
