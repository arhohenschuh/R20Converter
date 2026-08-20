# B071 - Prose compendium targets remain external

**Severity:** High
**Status:** Fixed in v1.14.0
**Found:** 2026-08-20 during frozen LMoP qualification

Module assembly localized direct executable `uuid` fields, but Actor/Item UUIDs inside Journal or
Item description strings remained external. When the custom donor existed, the module still
declared it only as a recommendation even though clicking the embedded target required it.

The assembler now scans strings for valid Actor/Item compendium UUIDs, clones resolvable donors,
and rewrites those references to local packs. Provenance fields are excluded; unresolved prose
links remain recommendations. Direct executable fields still fail closed when unresolved.