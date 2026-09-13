# B110 - World Macros resolve compendium links before Items exist

**Severity:** High
**Status:** Fixed (v1.15.17)
**Release:** [R20Converter v1.15.17](https://github.com/arhohenschuh/R20Converter/releases/tag/v1.15.17)
**Found:** 2026-09-13 during the owner's manual Out of the Abyss world conversion
**Affected:** R20Converter 1.15.16, commit `57eddb7f1cc4687c36bcd2e9cbe82ff7a1489ffa`
**Component:** World branch of [R20Converter.convert](../../src/R20Converter.py), [Macro](../../src/entities/macros.py), and [Entity._foundCompendium](../../src/entities/base.py)

## Reported Failure

The GUI calls the world-conversion path, which constructs Macros before constructing the Items
collection. A Macro action containing a Roll20 compendium link reaches the resolver and aborts:

```text
R20Converter.convert: self.macros = Macros(self).save()
Macro.__init__: self.replaceCompendiumLinks(self.replaceEntityLinks(macro["action"]))
Entity._foundCompendium: item = converter.items.getByName(name)
AttributeError: 'R20Converter' object has no attribute 'items'
```

HTML compendium links trigger this directly; supported Markdown links reach the same resolver
after normalization. The affected path is world export, not the module branch used for the
earlier B107/B108/B109 acceptance. Disabling chat does not prevent the Macro failure. A partial
world left by the failed conversion is not a completed output.

## Root Cause And Repair

World mode initialized folders, then Macros and chat, and only then `Items`. Both link-producing
collections can require an Item lookup or import. Initialize the single Items collection and
its source entries immediately after folders, before either Macros or chat. Retain that same
collection through journal, Actor, and table construction and the final save; do not replace it
and lose Items imported while resolving links.

The existing resolver also passed an already normalized imported Item ID back through the
Roll20-link resolver, which normalizes IDs again. Once startup succeeds, that can discard the
newly created Item link. Pass the Item's original ID into that path so the resulting native
`@UUID[Item.<id>]` points to the actual saved Item. Do not suppress the AttributeError or remove
the compendium link to make conversion appear successful.

## Focused Coverage

[TestWorldInitialization](../../tests/test_conversion_log.py) covers Items-before-Macro/chat
ordering, preservation of link-imported Items, and world conversion with a real local spell
pack. The cases exercise HTML and Markdown Macro links, repeated/nested Macro entries, and
chat enabled or disabled. They require one saved imported Item, both Macro UUIDs targeting it,
an Item folder, the requested chat behavior, and a completed world manifest.

All six world-startup cases reproduce the exact reported `AttributeError` against an isolated
copy of the released v1.15.16 source, and pass with the repair. Two additional link tests cover
saved Item IDs in world and module links. The complete shipping Python 3.8 suite passes 1,023
tests with these eight additions.

Local evidence is retained under
`D:/Automation_Local/Work/DnD5e/Foundry_Work/r20converter-b110-001/`:

- `evidence/negative-v1.15.16.xml`: six rejected preceding-release controls.
- `evidence/negative-item-links-v1.15.16.xml`: two rejected saved-Item-ID controls.
- `evidence/final-source-suite-001.xml`: complete passing source suite.
- `evidence/versioned-suite-1.15.17.xml`: 1,023 passing tests on the versioned candidate.
- `world-fixtures-002/`: completed world fixtures with saved Macro/Item UUID relationships.

## Local Build Verification

The corrected executable is built beside the running v1.15.16 GUI at
`G:/Make/GitDev/R20Converter/build/R20Converter-1.15.17-win-amd64/`.
The earlier GUI and its build directory were not stopped or replaced.

Both Windows entry points report 1.15.17. The packaged CLI completes four real world-conversion
fixtures covering HTML/Markdown Macro links and chat enabled/disabled. Each output contains one
saved imported Item, two Macros with resolving native Item UUIDs, an Item folder, the expected
chat state, and a completed world manifest. Bundled-only `plyvel` also passes a write/close/reopen
check. The report is `evidence/local-build-1.15.17.json`.

The local ZIP is 189,735,884 bytes, SHA-256
`6E42A665E8A352C9AE9E24BCEA3D32FBBA984C93153F8BB160AC8A6A2B2275AC`.
Every archived file was compared with the unchanged local build. The artifact is retained under
`artifact/R20Converter-1.15.17-win-amd64.zip` in the evidence root above.

The owner authorized publication of this verified build. The complete OotA conversion has not
been rerun here, and no independent review or campaign acceptance is claimed. The already
published v1.15.16 bytes remain unchanged; the v1.15.17 publication receipt binds the archive,
release commit, annotated tag, and downloaded release assets.