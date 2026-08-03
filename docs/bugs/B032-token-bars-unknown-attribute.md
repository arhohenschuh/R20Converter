# B032: Unlinked token bars point at `attributes.bar1`/`bar2`, which the dnd5e schema drops

- **Status**: Open
- **Severity**: Major (unlinked token bars — the common NPC HP case — render empty)
- **Found**: 2026-08-03 audit
- **Component**: `src/entities/actors.py:354-372` (`Token.getDict`), `1031-1036` (`createActorAttributes`), `src/entities/scenes.py:303-318`

## Defect

A Roll20 token bar that is not linked to the `hp` attribute is converted as:

- token `bar1.attribute = "attributes.bar1"`,
- an ActorDelta carrying `delta.system.attributes.bar1 = {value, max}`,
- and (on the actor itself) `system.attributes.bar1/bar2` blocks.

This worked in the pre-v10 world where actor data was raw JSON and unknown keys
survived. Under v10+ DataModels, `NPCData`/`CharacterData` declare no
`attributes.bar1`/`bar2`, so:

- the actor-level blocks are dropped on load,
- the synthetic token actor built from the delta drops them too,
- `TokenDocument.getBarAttribute("bar1")` resolves `attributes.bar1` to
  `undefined` and the bar is not rendered.

Roll20 NPC tokens overwhelmingly carry their HP as **unlinked bar values**, so
without `--force-hp-for-token-bar1` most NPC tokens lose their HP bar, and the
per-token HP overrides (wounded monsters placed on maps) are lost with the
dropped delta.

## Suggested fix

- When a bar's values look like HP (or the actor is an NPC and the bar is the
  only bar), map the delta onto `system.attributes.hp.{value,max}` and point the
  bar at `attributes.hp` — i.e. make the `--force-hp-for-token-bar1` behaviour
  the default when the linked attribute cannot be represented.
- For genuinely custom bars, the 5.x-native representation would be a resource
  (`resources.primary/…`) or a bar pointing at an existing schema path; anything
  else cannot round-trip and should at least warn.
- Stop emitting `attributes.bar1/bar2` on the actor (dead keys in 5.x).
