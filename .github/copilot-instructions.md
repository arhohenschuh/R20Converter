# R20Converter Module-Agnostic Boundary

- Keep all R20Converter implementation and fixes module agnostic. Fix generic
  conversion behavior, not individual adventures or campaigns.
- Never select a repair by a specific module's name, ID, path, hash, or document
  identities. Do not hide module-specific exceptions in configuration, lookup
  tables, or otherwise generic helpers.
- Base fixes on reusable input structure, schema, and rule semantics. Equivalent
  inputs from unrelated modules must receive the same behavior.
- Any targeted repair needed only for one specific module must run separately
  after conversion, outside R20Converter. If a general rule cannot be established,
  keep the repair in that module's post-conversion pipeline.
- Real module examples may be regression fixtures, but tests must also cover the
  same behavior with different module/document identities and an unaffected
  control. Passing only the original module's case does not prove a generic fix.
- Defect reports and fix suggestions must distinguish generic converter defects
  from module-specific source or content corrections. Converter implementation
  and builds remain the repository owner's responsibility.

# Fork Boundary

- This repository is the fork `arhohenschuh/R20Converter`. Push, tag, release,
  and open issues or pull requests only there (`origin`).
- Never write to the upstream `kakaroto/R20Converter`: no pushes, tags, issues,
  pull requests, comments, or releases. `upstream` is for fetching only.
- The fork has GitHub issues disabled, and `gh issue create` falls through to
  upstream. Record defects in `docs/bugs/` (Bnnn register) instead.
- Pass `--repo arhohenschuh/R20Converter` to every `gh` command that writes.