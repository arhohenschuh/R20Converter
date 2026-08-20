# ADR-012: Assemble self-contained Adventure modules

- **Status**: Accepted
- **Date**: 2026-08-20
- **Supersedes**: downstream generic Adventure/art/dependency repair
- **Superseded by**: -

## Context

ADR-009 made module pack storage native and ADR-010 preserved each pack's folder tree, but a module
was still a set of independent compendiums. Importing them separately could regenerate IDs and
break Token-to-Actor links. Embedded HTML art and executable UUIDs could remain owned by Roll20 or
an optional custom compendium, contradicting the module's standalone claim.

## Decision

Every module export runs one assembly phase after all source documents exist and before pack save.
It:

1. localizes external executable Actor/Item targets or fails closed;
2. internalizes external document and HTML image references;
3. records non-executable external compendium references as recommendations;
4. writes ordinary recursive LevelDB packs;
5. writes one Adventure snapshot containing the same document IDs and folder tree.

The Adventure is the preferred import surface. Ordinary packs remain available for browsing and
selective import. Item-typed deck-card records join `Adventure.items`; no Card documents are
invented.

## Consequences

- A normal module import no longer needs a downstream Adventure builder or art internalizer.
- Existing asset download failure is release-blocking when an external reference cannot be owned;
  a broken local path is not accepted as graceful degradation.
- Executable dependencies are copied, not merely recommended. Prose and advancement links may
  remain external because they do not block using the converted activity.
- Campaign-specific RollTables, encounter tuning, aliases, and editorial organization remain
  downstream policy and are not inferred.
- Worlds retain NeDB and do not run this assembly phase.