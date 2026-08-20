# B073 - Adventure Journal hierarchy is not source-backed

**Severity:** High
**Status:** Fixed in v1.14.0
**Found:** 2026-08-20 during frozen LMoP qualification

The Adventure copied stored Journal folders without independently proving they represented the
immutable Roll20 `journalfolder` tree. Flattened, stale, or incompletely assigned pack state could
therefore become the canonical one-click import surface.

Assembly now projects the source tree before pack serialization. Folder IDs are deterministic from
source index paths; duplicate references, malformed folders, missing Journal documents, and any
coverage mismatch abort conversion. The same assignments feed the source pack and Adventure.