# B121: Compendium conversion rejects R20Exporter 1.5.2+ exports

- Severity: High
- Status: Open
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
