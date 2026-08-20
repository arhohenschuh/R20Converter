# B061 — Token name display varies by Roll20 flags

**Severity:** Minor
**Status:** Fixed in v1.11.2
**Found:** 2026-08-20 during *Curse of Strahd* owner review

## Defect

Actor prototype and placed Scene Tokens inherited Roll20's per-token `showname` and
`showplayers_name` flags. Equivalent converted creatures therefore varied between Never
Displayed, Always for Owner, and Always for Everyone. Owners could not identify some Tokens from
the canvas, while other names were exposed to every player.

## Evidence

The accepted *Curse of Strahd* candidate contained 1,097 placed Tokens: 539 used
`displayName: 0` and 558 used `displayName: 40`. All 181 Actor prototypes already used 40 because
their source defaults happened to resolve that way; the inconsistency was confined to placed
Tokens but originated in the shared Token serializer.

## Fix contract

- Serialize `displayName: 40` (Always for Owner) for every Token.
- Apply the same shared Token path to Actor prototypes and placed Scene Tokens.
- Preserve bar visibility, Actor ownership, Token identity, and all other Token fields.
- Cover conflicting hidden and player-visible Roll20 source flags with regression tests.