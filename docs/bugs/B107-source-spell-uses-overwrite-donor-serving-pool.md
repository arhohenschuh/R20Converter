# B107 - Source spell uses overwrite a donor serving pool and abort conversion

**Severity:** High
**Status:** Fixed (v1.15.16)
**Found:** 2026-09-13 during the fresh *Out of the Abyss* 1.5.0-rc.1 conversion
**Affected:** R20Converter 1.15.15, commit `3a121694e023b8506d81649183b4d12c1e6c5ccf`
**Component:** [Item.createItemFromCompendium](../../src/entities/items.py#L615), `Item.CHARACTER_STATE_KEYS`, `_mergeSpellConsumption`
**Related:** [B050](B050-pc-class-level-always-one.md), [B062](B062-compendium-overwrite-discards-spell-state.md), [B064](B064-actor-resource-contracts-incomplete.md)

## Defect

With `--no-compendium-overwrite`, a source spell's empty `system.uses` replaces a valid
compendium-owned pool while the donor activities that depend on that pool survive. The resource
validator then correctly rejects the merged Item and stops the entire campaign conversion.

The real failure occurs while converting Quenthel Baenre's **Heroes' Feast**. This donor uses
an Item pool to represent twelve servings created by the spell, not the caster's daily casting
allowance. The source spell row declares no daily-use limit. Its empty casting-use block must
not erase the donor's separate serving mechanic.

```text
Creating Character : Quenthel Baenre
Heroes' Feast / utilityHeroeFeas consumes item uses without a usable pool
Error converting campaign with R20Converter v1.15.15:
Heroes' Feast / utilityHeroeFeas consumes item uses without a usable pool
```

The converter exits with code 1 during Actor construction, before completing the module or
Adventure. The partial output is not a release candidate. This is unrelated to the source's
zero Map Pins, source-link warnings, or the separate Foundry data-path warning.

## Verified Evidence

- Exporter: R20Exporter **1.4.1**, campaign **Out of the Abyss**; exact archive size
  **1,352,746,871 bytes**, SHA-256
  `12E57C593791D75A94FE0F7590C84F34286CC0E9E6034A5D62915D7C16FF3462`.
- Converter: published **1.15.15** executable, SHA-256
  `BF43F5875B5A7BB8CDCC60A7DE4B96CFEFF9CC27A00329AAC414C6A17046049D`.
  The repository was clean at the affected commit before this documentation-only intake.
- Donor: accepted Beyond5e compendium **1.4.1**, archive SHA-256
  `67D4733D6F6B69C4897B80E5B5D46F26764EF53C1BB21F6C55C9ADC4094C47C5`;
  assets **1.1.0**, dnd5e **5.3.3**, 2014 rules. Heroes' Feast ID: `HeroesFeast14III`.
- Source Actor ID: `-LxlLhUgMC-7CqdiR5Lc`; source repeating spell row:
  `repeating_spell-6_-M1CyM7NVbJ3ZmvI-5vf`.
- The actual donor passes `_validateResourceContract` before merging. Its unchanged pool is
  `{"spent":12,"max":"12","recovery":[{"period":"sr","type":"loseAll","formula":""}]}`.
- `utilityHeroeFeas` / **Create Feast** consumes a spell slot and has a self `itemUses` target
  of `-12`, generating the servings. `healHealing1IIII` / **Consume Feast** has a self
  `itemUses` target of `1` and `spellSlot: false`.
- The accepted Out of the Abyss **1.4.4** baseline retains the same twelve-serving pool and both
  activities on Quenthel's embedded Item. This corroborates the serving mechanic; it does not
  independently validate every historical casting-method setting.
- A direct call to the unmodified repository implementation with the actual donor and a
  constructed empty source-use block reproduces the exact exception for both `method: "spell"`
  and `method: "innate"`. Execution used the selected Python **3.8** automation environment;
  bytecode writing was disabled. No repository implementation or donor was modified.

## Cause

1. [The spell state allowlist](../../src/entities/items.py#L491) includes `uses` alongside
   `method` and `prepared`. This was added to preserve genuine source casting limits for B062.
2. [The merge loop](../../src/entities/items.py#L633) assigns each allowlisted value wholesale:
   `item.entity["system"][key] = custom_data[key]`.
3. For this source, `custom_data["uses"]` is `{"spent":0,"max":"","recovery":[]}`.
   It overwrites the donor's serving capacity, spent count, and recovery rule.
4. Donor activities remain. `_mergeSpellConsumption` does not restore the overwritten pool;
   ordinary `method: "spell"` returns immediately from that helper.
5. [The resource validator](../../src/entities/items.py#L191) finds a self-use target but no
   usable Item pool and raises. Its rejection is correct: the defect is upstream in the merge.

The missing distinction is **source casting state versus donor-generated supplies or follow-up
resources**. A name-specific Heroes' Feast exception would hide that shared boundary problem.

## Minimal Reproduction

Run this snippet from the repository root with the existing test environment. It uses the
existing `FakeDatabase` helper and a minimal synthetic donor with the observed resource shape;
it needs no campaign archive, network access, or LevelDB opens. On affected code, both iterations
print the exact failure. A future fixed implementation should instead construct a valid Item.

```python
import copy
import sys
from pathlib import Path
from types import SimpleNamespace

sys.dont_write_bytecode = True
root = Path.cwd()
sys.path[:0] = [str(root / "src"), str(root / "tests")]
from conftest import FakeDatabase
from entities.items import Item, _validateResourceContract

donor = {
    "_id": "HeroesFeast14III",
    "name": "Heroes' Feast",
    "type": "spell",
    "img": None,
    "system": {
        "method": "spell",
        "uses": {
            "spent": 12,
            "max": "12",
            "recovery": [{"period": "sr", "type": "loseAll", "formula": ""}],
        },
        "activities": {
            "utilityHeroeFeas": {
                "_id": "utilityHeroeFeas",
                "name": "Create Feast",
                "type": "utility",
                "consumption": {
                    "spellSlot": True,
                    "targets": [{"type": "itemUses", "target": "", "value": "-12"}],
                },
            },
            "healHealing1IIII": {
                "_id": "healHealing1IIII",
                "name": "Consume Feast",
                "type": "heal",
                "consumption": {
                    "spellSlot": False,
                    "targets": [{"type": "itemUses", "target": "", "value": "1"}],
                },
            },
        },
    },
}
_validateResourceContract("spell", donor["name"], donor["system"])
for method in ("spell", "innate"):
    custom = {
        "method": method,
        "prepared": 1,
        "uses": {"spent": 0, "max": "", "recovery": []},
        "activities": {},
    }
    database = FakeDatabase(str(root), {"no_compendium_overwrite": True})
    try:
        Item.createItemFromCompendium(
            database, None, SimpleNamespace(entity=copy.deepcopy(donor)), custom
        )
    except ValueError as error:
        assert str(error) == (
            "Heroes' Feast / utilityHeroeFeas consumes item uses without a usable pool"
        )
        print(method, str(error))
    else:
        raise AssertionError("B107 was not reproduced")
assert donor["system"]["uses"]["max"] == "12"
```

## Repair Constraints

The following constraints bound the converter repair and its acceptance.

- Resolve spell resource ownership before assigning source `uses`. Determine whether the donor
  pool is a casting quota or a generated resource used by preserved follow-up activities.
  A negative self-use producer together with positive follow-up consumers is relevant evidence
  for the latter; qualify the pattern with tests rather than matching the spell name.
- When the source declares no casting-use limit and the retained donor activities require a
  valid generated-resource pool, preserve the complete donor `uses` contract: `max`, `spent`,
  and `recovery`. Continue preserving the source `method` and `prepared` fields.
- Do not merely retain every nonempty donor pool. Genuine source casting limits, at-will and
  ritual rules must still override donor casting defaults as required by B062.
- Review `_mergeSpellConsumption` with this distinction. Changing casting method must not
  remove a serving consumer or reinterpret serving capacity as a daily casting allowance.
  For standard casting, Create Feast must still consume the cast's slot and generate twelve
  servings; Consume Feast must spend one serving without another slot.
- If a finite source casting quota and a separate donor supply pool are both required, model
  them as distinct native resources or reject the unresolved conflict explicitly. Do not merge
  both meanings into one `system.uses` counter or silently discard either.
- Keep `_validateResourceContract` enabled and rerun it after the resolved merge. Do not solve
  the crash by deleting the activity targets, removing Heroes' Feast, or weakening validation.

## Regression And Acceptance

Extend [the existing spell-state tests](../../tests/test_asset_and_compendium_fixes.py#L531),
reusing their helpers rather than adding a separate framework.

1. Valid generated-pool donor plus empty source casting uses: successful merge, full serving
   pool preserved, source method/preparation preserved, donor template unchanged.
2. Standard cast: negative `-12` producer and positive `1` consumer retained; only the initial
   cast spends a spell slot. Test other source casting methods separately without inventing
   their slot policy from the historical module.
3. Genuine source limited-innate quota and ordinary empty donor pool: preserve the existing
   B062 behavior, including one valid casting consumer and correct recovery.
4. Source quota plus generated donor pool: prove separate counters, or require a specific
   unresolved-resource error rather than a superficially green but conflated result.
5. Missing/zero donor pool with a retained self-use target must still fail. Existing double
   slot/use, ambiguous primary, at-will, ritual and negative-production controls must remain valid.
6. Execute the exact fresh OotA export through the qualified converter. Quenthel's Heroes'
   Feast must no longer abort conversion. Verify the embedded Item and Adventure projection,
   then exercise create/consume behavior and persisted counter changes in isolated dnd5e 5.3.3.
   Whole-adventure completion may still expose independent defects; this report does not clear them.

## Retained Evidence

Large or private source artifacts remain outside Git. The local evidence root is:

```text
D:/Automation_Local/Work/DnD5e/Foundry_Work/out-of-the-abyss-1.5.0-rc.1-reexport-002
```

| Relative Path | Purpose |
| --- | --- |
| `reports/new-source-admission-001.json` | Exact export identity, source collection and asset admission |
| `reports/pipeline-preparation-001.json` | Pinned converter/dependency identities and isolated roots |
| `build/conversion-log.txt` | Actual failed conversion and exact Heroes' Feast error |
| `reports/driver-conversion-001.json` | Failed-stage receipt and hashes of driver output logs |
| `reports/heroes-feast-converter-probe-001.json` | Actual donor, source row, accepted baseline Item and source identity |
| `tools/probe-converter-resource.mjs` | Source/donor inspection using disposable pack copies only |

## Implemented Resolution

The merge now identifies a generated supply by finite negative self-use production and a separate
positive, explicitly non-slot-consuming follow-up. Before copying character state, it preserves
that donor's complete pool if the source has neither a casting capacity nor a positive self-use
consumer. Competing resources raise a specific conflict. Source method/preparation still win,
and the existing consumption merge disables slots for non-slot source methods. The validator
distinguishes supply follow-ups from limited-innate casting consumers, but still rejects missing
pools and ordinary double consumption.

### Historical B107-Only Candidate

The measurements below belong to the retained B107-only candidate, before B108 was added to the
same unpublished release version. They do not identify the final combined release archive.

Measured on 2026-09-13: all six initial B107 cases failed on the unchanged implementation; the
completed character-state slice passes 41 tests and the shipping Python 3.8 suite passes 988.
The released 1.15.15 binary fails the unchanged Quenthel fixture with the exact B107 error; the
candidate converts it with equal Actor/Adventure Item and effect data. Its source `at-will` row
emits `method: innate`, `prepared: 1`, no casting slot, and the intact twelve-serving pool. The
eleven resulting Actors include ten localized summon dependencies, not additional source Actors.

The full exact export passes Quenthel, then stops on [B108](B108-limited-innate-blindness-deafness-primary-rejected.md),
which also reproduces in published 1.15.15. No source/donor workaround or whole-campaign PASS is
claimed. The exact extracted 1.15.16 executable confirms the same full-source boundary.

The frozen Quenthel fixture passes native Adventure import and reload in Foundry 14.367 / dnd5e
5.3.3 Legacy. Four native Actor-sheet activity clicks pass: Create/Consume for the actual source
method and for a separate standard-casting control. Production changes `spent` from 12 to 0;
consumption changes it to 1, leaving eleven servings. Quenthel's sixth-level slots stay at 2;
the standard control goes from 2 to 1 on creation and stays at 1 on consumption. Browser reload
and a fresh read of stopped LevelDB copies confirm those values. Native cleanup restores the
original Actor/Item systems and message/Actor ID sets; stopped storage confirms the serving pool
is back at `spent: 12` and the temporary control is absent.

The exact ZIP is 189,733,314 bytes, SHA-256
`DCAB361793F225F43DC4F65DA39C777AB33D4EBF7D2418B6242763AC546099BF`.
All 3,641 extracted files / 484,036,647 expanded bytes match the unchanged frozen build. Both
entry points report 1.15.16. With site-packages disabled and imports restricted to the bundle,
its native `plyvel` writes, closes, reopens, and reads the expected value. The preceding bundle's
extra `stderr.log` is absent; no dependency path was dropped.

The B107-only independent review passed four targets with no findings. Its exact archive remains
retained as superseded evidence; these records do not assert publication of that candidate.

Converter-owned evidence: `D:/Automation_Local/Work/DnD5e/Foundry_Work/r20converter-b107-001/`.
The input hashes are in `evidence/inputs.json`; full-source failure, targeted successful projection,
and published negative controls each have their own retained run directory and `replay.json`.

### Historical B107/B108 Candidate

The owner subsequently authorized B108 repair and publication in the same 1.15.16 release. The
combined source passes 56 character-state and 1,003 full Python 3.8 tests. An unchanged two-Actor
fixture preserves both repaired spells and their Actor/Adventure Item/effect equality. B108 is
now fixed; the full export's later wildcard module-art failure is tracked separately as
[B109](B109-wildcard-module-assets-not-internalized.md). Final combined artifact and independent
review identities are retained under `r20converter-b108-001`, not the historical ZIP above.

The superseded two-fix candidate ZIP SHA-256 is
`E87065D05C32747C7AA773BC49B6FEEB52B308E6EC258A8C832EA018A9735BE0` (189,733,968 bytes).
All four B107 native workflows pass again alongside the four B108 workflows using output from
the exact extracted release executable. Reload, stopped persistence, native restoration and
stopped cleanup pass for both source Actors and their temporary controls. See
[B108's historical acceptance record](B108-limited-innate-blindness-deafness-primary-rejected.md)
for the combined evidence paths and remaining full-campaign limitation.

### Final Three-Fix Release

The owner added B109 before publication, then waived Opus review and assigned full conversion-
pipeline testing downstream. All 1,015 Python 3.8 tests pass with the three fixes. The final build
is recorded under `r20converter-b109-001`; neither earlier ZIP hash is its identity, and neither
prior review covers the added wildcard implementation. No new full-campaign acceptance is claimed.