# B121: Compendium conversion rejects R20Exporter 1.5.2+ exports

- Severity: High
- Status: Fixed in v1.16.3
- Observed release: R20Converter 1.16.2, commit 9c485df
- Reported: 25 October 2026, Witchlight reconversion (`witchlight/v120`)

## Reproduction

Run any campaign conversion with `--convert-compendium --compendium-zip <book>-compendium-1.5.2.zip`,
where the ZIP comes from R20Exporter 1.5.2 or 1.5.3. Conversion aborts before any output:

```text
Compendium export: unsupported capture format or scope
  File "src\compendium_export.py", line 217, in _load
    _require(manifest.get("capture_format") == "dom-serialized-html-and-ordered-attributes"
```

The observed archive is complete (`status: complete-within-index`; 89/89 pages, 105/105 assets,
no issues or failures) and uses `R20Compendium_format: "1.0"` with
`capture_format: "dom-serialized-html-and-ordered-attributes"`. Only the scope differs:

| Field | R20Exporter 1.5.0/1.5.1 | R20Exporter 1.5.2+ |
| --- | --- | --- |
| `compendium.json` / `export_report.json` `scope` | `selected-index-and-direct-links` | `selected-book-catalogue-and-navigation` |

## Root Cause

`CompendiumExport._load` accepts exactly one scope string. R20Exporter 1.5.2 (commit `463bb1a`)
renamed the scope when it began following source-tagged appendix catalogues and native book
navigation. 1.5.2 also adds `requestAliases`, a `discovery` report block
(`pageRequests`, `aliases`, `excludedLinks`) and per-link discovery records; 1.5.3 continues
navigation through empty entries, which are reported as `empty-compendium-entry` issues. The
converter predates all of these.

## Expected Behavior

- Accept both scopes. Keep the existing identity, hash, size, path, duplicate and page-order checks.
- Treat `requestAliases` as verified alternative request URLs for the same captured page. They must
  resolve link targets, not duplicate Journals or assets.
- Do not regress the existing rejection of partial captures. Decide explicitly whether
  `empty-compendium-entry` issues remain a rejection or become a reported, non-blocking omission.
- Record the accepted scope in `flags.R20Converter.compendium` and the conversion report.

## Regression Requirements

- One 1.5.1-style archive (old scope) and one 1.5.2-style archive (new scope, aliases and nested
  catalogue pages) both convert to the same Journal structure for equivalent pages.
- An alias of a captured page resolves to that page's local UUID, with no duplicate Journal.
- An unknown scope string and a partial capture still fail closed.
- Use synthetic book identities; do not key the fix to Witchlight.

## Triage And Generic Resolution

This is a reader compatibility defect, not a damaged book export. Both known scope strings are
accepted under the same R20Compendium 1.0 payload contract. Existing identity, size, hash, path,
duplicate-member, and page-order checks remain in force.

Catalogue aliases are checked against a captured canonical request, matching numeric page ID
and expansion, permitted URL origins, unique request identities, non-conflicting response
mappings, and matching discovery counts. They populate link lookup only; no new Journal or
asset is created. The accepted scope is written to `flags.R20Converter.compendium.captureScope`
and the `compendium` section of `conversion-report.json`.

**Empty-entry policy:** incomplete captures remain rejected, including exports with failed
`empty-compendium-entry` records. The reader does not silently omit failed pages or claim
complete coverage. Unknown scopes and malformed aliases also fail closed.

The regression suite covers old/new scope conversions in world/module modes, nested catalogue
pages, different synthetic book identities, alias links and conflicts, cross-expansion URLs,
discovery counts, and partial captures. Tests live in
[test_compendium_export.py](../../tests/test_compendium_export.py).

The original reported 1.5.2 ZIP was tested without the downstream scope shim:
SHA-256 `19432DB68CBFF9C3D9136CE13538C6FA130A23CB160AEBE776295740967EE790`,
169,242,516 bytes. Its 89 captured pages, eight aliases, 105 bundled asset records,
106 rendered image references, and 91 captured internal links pass world/module conversion;
module Journals match the Adventure projection. Published v1.16.2 rejects this exact ZIP before
output creation. The tests use a minimal campaign fixture, not a full campaign replay.

Evidence is retained under
`D:/Automation_Local/Work/Tooling/r20converter/v1163-b121/Reports/`.

## Frozen And Native Verification

The v1.16.3 archive passes both entry-point checks, frozen-code/document parity, bundled
dependency and native LevelDB checks, old-scope world/module controls, and the same real
1.5.2 archive in world/module output. The complete source suite passes 1,237 tests.

Foundry 14.369 with dnd5e 6.0.6 imports the exact frozen module into an empty disposable world.
All 90 Journals are present, including 89 unique reference pages. All eight aliases resolve
through native UUID lookup and enrich as links without broken targets; 104 unique local image
paths return successfully. State and alias resolution survive reload.

Stopped-database checks confirm reciprocal Journal/Page relationships, persisted capture scope,
and content equivalence. Foundry trims outer whitespace, serializes CSS declarations, and removes
empty style attributes; these measured formatting changes are not byte-identical HTML and are
normalized only by the persistence verifier. No converter output was repaired for acceptance.
This remains a minimal-campaign reference-content test, not a full Witchlight campaign claim.
