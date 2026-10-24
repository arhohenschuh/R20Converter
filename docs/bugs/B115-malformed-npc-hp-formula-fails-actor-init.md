# B115: Malformed NPC HP formula makes the Actor fail to initialize

- Severity: High
- Status: Fixed in v1.16.2 for NPC HP formula emission
- Observed release: R20Converter 1.16.1, commit cbb0d0e7a9665c43f780c26d3f31ef98f853454d
- Reported: 24 October 2026, Dragoncoast Danger played-world reconversion (`dcd/v130`)

## Reproduction

Source NPC Zybilna (Dragoncoast Danger R20Exporter 1.5.3) has
`npc_hpformula = "22d8 + 22)"`, with an unbalanced closing parenthesis. The converter copies it
verbatim to `system.attributes.hp.formula`. After Foundry 14.369 / dnd5e 6.0.6 migrates the
world, the actor fails validation and is excluded from `game.actors`:

```text
Error: Failed to initialize Actor [Actor.NGEyY2Q0OTUwNzI0]:
  system.attributes.hp.formula: Expected ".", "[", [%*/], [+\-], [0-9], [dD], or end of input but ")" found.
```

The world opens with 87 of 88 actors. Offline gates did not detect it because the formula
scanner does not check `hp.formula`.

## Expected Behavior

The converter validates every formula field it emits against the dnd5e formula grammar.
An HP formula that cannot be parsed is not written. The converter logs an explicit warning
with the source character and value, keeps the explicit `hp.max`, and never repairs by
guessing.

## Regression Requirements

- An NPC with an unbalanced or otherwise unparseable HP formula converts. The actor
  initializes, `hp.max` is preserved, and a warning names the field.
- A valid formula (`22d8 + 22`) is unchanged.

## Downstream Disposition

Dragoncoast Danger corrected the single source value to `22d8 + 22` post-conversion. Its
average, 121, equals the source HP maximum.

## Generic Resolution

The existing dice/reference arithmetic validator now checks expression structure without
evaluating it. NPC HP emission clears an invalid formula and logs its source field/value, while
retaining the explicit HP maximum. It does not guess the missing punctuation or recalculate HP.
Valid dice, arithmetic, and supported dynamic references remain supported. This resolution is
bounded to the reported HP field; it is not a claim that every possible third-party formula
language has been implemented. See [test_actor_hp.py](../../tests/test_actor_hp.py).
