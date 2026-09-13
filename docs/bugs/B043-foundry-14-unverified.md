# B043: Foundry 14 support — what is out of the box and what is not

- **Status**: Storage limitation resolved; a native-v14 target profile remains planned
- **Severity**: Informational (output loads on Foundry 14)
- **Found**: 2026-08-03, verifying 1.0.2 against the reporter's live install
- **Component**: `src/foundry.py` (`MINIMUM_CORE_VERSION`, `VERIFIED_CORE_VERSION`,
  `DOCUMENT_SCHEMA_CORE_VERSION`), pack writing in `src/module.py` / `src/world.py`

## Why this was opened

The converter declared Foundry generation 13 everywhere. The reporter runs
14.365. The stated goal is a converter whose output needs no repair pipeline:
previously a campaign had to be converted with an older build, fixed offline,
imported so Foundry and dnd5e could migrate it, then fixed and tested again
before packaging.

## Measurement

The reporter supplied both the input and the output of that pipeline: the
*Lost Mine of Phandelver* Roll20 export, and `lost-mine-of-phandelver-1.2.0`,
the module that came out of it and runs on Foundry 14.365 with dnd5e 5.3.3.
Converting the same export with 1.1.0 and comparing document by document:

**Actors — 37 matched by name.** Every `system` key present in the hand-repaired
module is present in the converter's output; none is missing. `details.cr`,
`attributes.hp.value`, `attributes.ac.flat` and `traits.size` are identical
throughout. The differences that remain all run the *other* way:

| field | hand-repaired module | converter 1.1.0 |
| --- | --- | --- |
| `spells.spellN` | `{value, max, override}` | `{value, override}` — `max` is retired (B030) |
| `attributes.spell` | absent | `{level: N}` — the field NPC slots derive from |
| `details.type` | `"humanoid (goblinoid)"` (15/37) | `{value: humanoid, subtype: goblinoid}` (B041) |
| `tools` | absent | `{}` — declared by `CreatureTemplate`, empty for NPCs |

So the module that took a manual pipeline to produce still carries B030 and
B041. Out-of-the-box 1.1.0 output is ahead of it on document content.

## Fixed in 1.1.0

`compatibility.verified` is now `14`, which is what the reference module
declares (`minimum: 13, verified: 14`). This is a compatibility claim backed by
the comparison above, and it is what stops Foundry 14 flagging the package as
unverified.

`DOCUMENT_SCHEMA_CORE_VERSION` deliberately stays at **13**. It is what Foundry
compares against the running build to decide which migrations to run, and
claiming 14 makes it *skip* them — including the NeDB→LevelDB conversion the
output depends on. A world declaring 14 while shipping NeDB files would open
empty. The declaration is accurate, and it is load-bearing.

## Storage Resolution

The historical module-pack blocker was resolved by ADR-009 and the native LevelDB reader/writer.
Current module output ships LevelDB directories, including recursive embedded-document
relationships. B031 is also fully resolved; its old partial status must not be carried forward.

World output deliberately retains the established NeDB migration path and core-13 document
stamps. This is not an outstanding module-pack bug. Promoting a separate native-v14 target
profile is a future feature governed by the roadmap's migration-parity gates, not a reason to
change working storage declarations during this patch release.

## Residual risk

The historical document comparison above was not an exhaustive compatibility census. Current
release acceptance must use the pinned installed Foundry and dnd5e runtime; passing a focused
conversion does not establish full-campaign or every-version compatibility.
