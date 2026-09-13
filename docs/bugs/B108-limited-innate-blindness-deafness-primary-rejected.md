# B108 - Limited-innate Blindness/Deafness cannot select a donor primary

**Severity:** High
**Status:** Fixed (v1.15.16)
**Found:** 2026-09-13 during the B107 exact-source replay
**Affected:** R20Converter 1.15.15 and the 1.15.16 B107 candidate
**Component:** `_mergeSpellConsumption` in [items.py](../../src/entities/items.py)
**Related:** [B077](B077-donor-activity-mismatch-drops-innate-consumer.md), [B107](B107-source-spell-uses-overwrite-donor-serving-pool.md)

## Reproduction

The fresh Out of the Abyss R20Exporter 1.4.1 archive, SHA-256
`12E57C593791D75A94FE0F7590C84F34286CC0E9E6034A5D62915D7C16FF3462`, reaches
Deep Gnome (Svirfneblin) after the B107 repair and fails with:

```text
Cannot select one primary donor activity for limited innate spell 'Blindness/Deafness'
```

Dependencies are accepted Beyond5e 1.4.1, assets 1.1.0, dnd5e 5.3.3, and 2014 rules.
The converter flags use additive custom-precedence enrichment and `--no-compendium-overwrite`.
This occurs in the existing primary selector, not the B107 generated-supply classifier.

A collection-filtered fixture keeps the selected Deep Gnome record and every original asset
member unchanged. The published 1.15.15 standalone executable also exits 1 on that fixture with
the exact same error. Thus this is a pre-existing blocker exposed after Quenthel, not a regression
introduced by the B107 patch. No generated module from the failed full run is an RC.

## Evidence And Scope

Local evidence root: `D:/Automation_Local/Work/DnD5e/Foundry_Work/r20converter-b107-001/`.

- `source-001/conversion.log`: full exact-source failure and traceback.
- `source-001/replay.json`: candidate source command and exit 1.
- `evidence/deep-gnome-fixture.json`: unchanged source Actor identity and fixture hash.
- `deep-gnome-published-control-001/replay.json`: exact published-baseline negative control.

## Root Cause And Fix

The accepted donor `BlindnessDeafn14` has two complete casting alternatives, **Blindness: Initial
Save** and **Deafness: Initial Save**, with the same Constitution-save and activation data but
different effect targets. Its two **Recurring Save** activities are free, end-of-turn follow-ups.
The source Deep Gnome (`-LxlagUiiUsS73QEL9lv`) declares `1/day` in repeating row
`repeating_spell-2_-LxlaglA0V895U61NMH0`. The selector recognized alternative placement geometry
but not these alternative effects, so neither initial cast could become a bounded primary.

`_alternativeInitialSaveActivities` now requires an exact set of slash-delimited spell-title
choices labelled `: Initial Save`, unique names, save activities with explicit one-action
activation, no damage, identical non-display activity data, and one distinct failed-save effect
per choice. Selection and validation use the same qualification. It is not a spell-name special
case, a blanket multi-consumer exemption, or permission to treat sequential saves as alternatives.

Both initial choices receive one positive self `itemUses` target drawing from the source pool.
The pool remains `spent: 0`, `max: "1"`, daily `recoverAll`; method and preparation remain source-
owned. Both recurring activities retain no resource targets and `spellSlot: false`. All four
activities and both condition effects remain present, with unchanged donor/source inputs.

## Pre-B109 Validation

- Both new positive cases failed on the unchanged selector with the exact B108 error.
- Fifteen B108 regressions cover both source activity shapes, mismatched titles/labels/effects/
	mechanics, generic title matching, and duplicate-consumption rejection.
- All 56 character-state tests and 1,003 shipping Python 3.8 tests pass with B107 and B108 combined.
- The real unchanged Deep Gnome fixture passes; the previous B107-only frozen candidate still
	fails it. The combined Quenthel/Deep Gnome fixture passes Item/effect and parent-child parity
	between Actor packs and the native Adventure.
- The exact full export passes both repaired spells and reaches the separate, pre-existing
	[B109](B109-wildcard-module-assets-not-internalized.md) module-art limitation. No full-campaign
	acceptance or source/donor workaround is claimed.

Current evidence root: `D:/Automation_Local/Work/DnD5e/Foundry_Work/r20converter-b108-001/`.
`evidence/b108-oracle.json` retains the real donor and source row. `deep-gnome-source-001`,
`deep-gnome-b107-only-control`, and `paired-source-001` retain the respective conversion/projection
receipts; `evidence/full-suite.xml` records the test result. Frozen and independent release gates
are recorded separately from these source-level measurements.

## Historical Two-Fix Candidate

These measurements predate the B109 fix and identify the superseded B107/B108-only build, not the
final three-fix release archive.

The combined 1.15.16 ZIP is 189,733,968 bytes, SHA-256
`E87065D05C32747C7AA773BC49B6FEEB52B308E6EC258A8C832EA018A9735BE0`.
All 3,641 files / 484,038,722 expanded bytes match the unchanged standalone build after extraction.
Both entry points report 1.15.16, and bundled-only native `plyvel` passes a close/reopen round trip.
The extracted executable converts the unchanged paired source Actors into twelve Actors including
ten localized summon dependencies, with complete affected Item/effect parity in the Adventure.

Foundry 14.367 / dnd5e 5.3.3 Legacy imports and reloads that exact output. Eight native Actor-sheet
workflows pass: the B107 source/standard Create/Consume cases, and each B108 initial/recurring
pair. Either initial B108 choice spends exactly one Item use; both recurring saves remain usable
after the pool is exhausted and spend nothing further. A separate attempt to use the other initial
choice against the exhausted original pool is rejected without resource changes or a new message.
No ordinary spell slot is spent for these limited-innate casts.

Reload and stopped LevelDB copies preserve the observed counters. Native cleanup restores the
original systems, Actor/message ID sets, and pools; stopped storage confirms both temporary
controls are absent. Owner acceptance runs used only the isolated `r20converter-b108` world on
port 30023. The classifier census recognizes exactly this donor among 492 pinned spells.

Evidence includes `paired-exact-001/replay.json`, `evidence/archive.json`, `evidence/exact-smoke.json`,
and `evidence/runtime-{import,clicks,verify,stopped,cleanup,restored}.json`. The full exact executable
still reaches B109 as described above. Independent review and publication receipts bind the final
archive separately; this record does not substitute for those gates.

## Final Release

B109 was subsequently repaired in the same unpublished 1.15.16 version. All 1,015 final Python 3.8
tests pass, including the unchanged B108 controls. At the owner's instruction, the final build
skips Opus review and leaves full conversion-pipeline testing downstream. The historical native
results above are retained without claiming a new whole-campaign or final-build runtime pass.
The final artifact and publication receipt live under the `r20converter-b109-001` work record and
the standard toolchain candidates directory.