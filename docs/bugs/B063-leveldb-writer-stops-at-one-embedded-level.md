# B063 - LevelDB writer stops at one embedded level

**Severity:** High
**Status:** Fixed in v1.12.0
**Found:** 2026-08-20 while planning recursive module-pack ownership

## Defect

`leveldb_pack.splitDocument()` split only the primary document's direct children. An Actor Item
became `!actors.items!<actor>.<item>`, but its ActiveEffects stayed inline. Scene Tokens likewise
kept their ActorDelta object inline rather than referencing a
`!scenes.tokens.delta!<scene>.<token>.<delta>` child.

Foundry stores embedded relationships recursively. The stale writer therefore produced plausible
LevelDB keys while losing the relationship indexes needed to load deeper children. First launch
could report missing singleton ActorDeltas or leave standalone Actor-pack Items with empty effect
indexes.

## Fix contract

- Split every declared embedded path recursively and include every ancestor id in the key.
- Preserve ordered id arrays and singleton ids according to field cardinality.
- Give an id-less ActorDelta the stable owning Token id; reject every other missing child id.
- Reject duplicate keys and duplicate child ids before replacing an existing pack.
- Fold deepest-first and reject inline, missing, conflicting, or orphaned relationships.
- Keep world NeDB output unchanged.

## Regression coverage

`tests/test_leveldb_pack.py` asserts recursive ActiveEffect keys, singleton ActorDelta keys, deep
round trips, parent order, bidirectional conservation, duplicate rejection, and non-destructive
validation. The v1.12.0 shipping suite passes 839 tests under Python 3.8 with native `plyvel`.