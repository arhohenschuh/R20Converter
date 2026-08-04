# B046: NPC special senses keep "passive Perception", and a list is mutated while iterating

- **Status**: Fixed in 1.7.0 (F046)
- **Severity**: Minor (cosmetic: a junk sense string on NPC sheets)
- **Found**: 2026-08-04, by a regression test written for B044
- **Component**: `src/entities/actors.py` (`createAttributeSenses`, special-sense extraction)

## Defect

```python
npc_senses = list(map(lambda x: x.strip(), npc_senses))
for i, sense in enumerate(npc_senses):
    if sense.strip().startswith("passive perception"):
        npc_senses.pop(i)
        continue
    for senseType in senseTypes:
        if senseType in sense.lower():
            npc_senses.pop(i)
            break
```

Two independent mistakes in six lines:

1. **Case-sensitive comparison.** Roll20 prints `passive Perception 13`; the guard
   tests `startswith("passive perception")`. The surrounding code lowercases
   `npc_senses` for the *regex* pass above but not for this one, so the guard
   never fires on real data.
2. **Mutating the list while enumerating it.** `pop(i)` shifts every later element
   down one while the loop counter keeps advancing, so the entry immediately after
   a removed one is skipped entirely.

Together these mean a stat block reading

```
darkvision 60 ft., passive Perception 12
```

removes `darkvision 60 ft.` at `i = 0`, then the loop ends because the list is now
shorter — leaving `system.attributes.senses.special = "passive Perception 12"` on
the NPC. Passive Perception is not a sense; dnd5e derives it from Wisdom.

Because Roll20 almost always prints at least one real sense before the passive
score, defect 2 hides defect 1: even a case-insensitive check would have been
skipped for the common input.

## Suggested fix

Build a new list instead of removing from the one being iterated, and compare
case-insensitively:

```python
kept = []
for sense in npc_senses:
    sense = sense.strip()
    if not sense:
        continue
    lowered = sense.lower()
    if lowered.startswith("passive perception"):
        continue
    if any(senseType in lowered for senseType in senseTypes):
        continue
    kept.append(sense)
special = ", ".join(kept)
```

## Regression tests

- `passive Perception 14` alone yields `special == ""` (case-insensitivity).
- `blindsight 10 ft., darkvision 60 ft., passive Perception 13` yields
  `special == ""` and both ranges parsed (the skip).
- `darkvision 120 ft., tremorsense 30 ft., keen hearing` yields
  `special == "keen hearing"` — a genuine special sense still survives.

## How it was found

Writing the B044 regression suite, not by reading the code. The test asserting
"passive Perception is not a special sense" failed against the *pre-existing*
implementation. This is the B011 lesson again: the defect sat in territory the
513-green suite never asserted on.
