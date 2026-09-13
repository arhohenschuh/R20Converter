# B109 - Wildcard module token images are treated as literal files

**Severity:** High
**Status:** Fixed (v1.15.16)
**Found:** 2026-09-13 after both spell fixes passed in the exact OotA conversion
**Affected:** Published 1.15.15 and the superseded B107/B108-only 1.15.16 candidate
**Component:** `ModuleAssembler._copyExternalAsset` in [module_assembly.py](../../src/module_assembly.py)

## Failure And Cause

During module assembly, the exact Out of the Abyss export reaches this error:

```text
could not internalize module asset modules/beyond5e-2014-assets/images/tokens/mm24-cat-*.webp
```

The pinned Beyond5e assets 1.1.0 ZIP and its disposable extraction both contain
`mm24-cat-01.webp` and `mm24-cat-02.webp`. This is not missing input art. `_copyExternalAsset`
passes the wildcard path to `os.path.isfile`, receives false, and returns no localized path;
`_internalizeString` then fails closed. The routine never expands or preserves a token family.

A focused reproduction runs the same input through the current class and the class reconstructed
from the committed 1.15.15 source archive. Both raise the identical error while the two matching
files are present. This is separate from B107/B108; neither spell fix touches module asset copying.

## Evidence And Repair Boundary

Evidence: `D:/Automation_Local/Work/DnD5e/Foundry_Work/r20converter-b108-001/`.

- `full-source-001/conversion.log`: exact-export module-assembly failure after Actor construction.
- `evidence/b109-probe.json`: baseline/current reproduction, concrete file identities, source archive hash.
- `evidence/inputs.json`: pinned export and dependency identities.

## Resolution

The owner added B109 to the same unpublished 1.15.16 release. Module-local patterns with a fixed
file extension now expand through Python's filesystem glob support. Every matching file is copied
under a deterministic family prefix derived from the source pattern, with a separate numbered
member even when two files contain identical bytes. Returned local wildcard paths match exactly
that family; `randomImg` and the other Actor/Token fields are not changed. No transcoding, single-
image substitution, or donor/source workaround is performed.

The copier rejects no-match families, empty or known-placeholder members, donor path escape,
output path-limit violations, content collisions, and stale output members. It verifies existing
files before reuse and preserves the existing literal-file and external-URL paths. Repeated
internalization is idempotent, including a new lookup of the original external pattern.

## Verification And Release Scope

Both new dedup-mode controls fail on the original implementation. Twelve B109 regressions pass,
and the complete module-assembly slice passes 35 tests. The full shipping Python 3.8 suite passes
1,015 tests with B107, B108 and B109 together. A real-asset probe verifies both exact pinned image
bodies, unchanged donor files, random-image data and Adventure parity; the committed 1.15.15
assembly code rejects that same pattern before the fixed code succeeds.

Current evidence: `D:/Automation_Local/Work/DnD5e/Foundry_Work/r20converter-b109-001/`.
`evidence/actual-wildcard.json` records the source/output identities and rejected preceding release;
`evidence/full-suite.xml` records the suite. Build, archive and publication receipts are separate.

The owner explicitly waived Opus review and assigned full conversion-pipeline testing to the
downstream workflow on 2026-09-13. This release therefore does not claim final whole-OotA or live
wildcard acceptance. Earlier B107/B108-only artifacts and review packets remain superseded evidence;
they must not be presented as an independent review of this final three-fix build.