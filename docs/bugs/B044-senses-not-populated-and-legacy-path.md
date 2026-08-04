# B044: Player-character senses are never populated, and senses use the pre-5.3 path

- **Status**: Schema fixed in 1.7.0 (F044). **PC senses remain unfixed** — see "Field result" below.
- **Severity**: Major (player-visible — darkvision does not work; PCs are blind on unlit scenes)
- **Found**: 2026-08-04, live diagnosis against *Wardens of the North* on Foundry 14.365 / dnd5e 5.3.3
- **Component**: `src/entities/actors.py:956-989` (`createAttributeSenses`), `:324-331` (`prototypeToken.sight`)

## Symptom

On a scene with `environment.darknessLevel = 1` and `globalLight.enabled = false`,
player characters see nothing — including races that should have darkvision.
Placing a light near the token is the only thing that reveals anything, because
`lightPerception` is the only detection mode left doing any work.

## Defect 1 — senses are parsed for NPCs only

```python
def createAttributeSenses(self):
    senses = {"darkvision": 0, "blindsight": 0, "tremorsense": 0, "truesight": 0,
              "units": "ft", "special": ""}
    if self.isNPC():          # <-- everything below is NPC-only
        ...parse npc_senses...
    return senses
```

Every **character** actor therefore emits all-zero senses. There is no code path
that can ever give a PC a non-zero `darkvision`.

This matters more than it looks, because vision modules derive token vision from
the **actor's senses**, not from the token's own sight range. With `darkvision: 0`
vision-5e correctly computes a darkvision range of 0, so the token falls back to
light perception alone.

The converter already reads Roll20's per-token night-vision distance — it lands in
`prototypeToken.sight.range` via `max(self.dim_sight, self.bright_sight)`
(`actors.py:328`) — but that value is never propagated into
`system.attributes.senses`. The two are independent, and only the senses side is
consulted by vision modules.

### Measured

*Wardens of the North*, all 6 player characters, read from the live world:

| PC | Race | Expected darkvision | `senses.ranges.darkvision` | `prototypeToken.sight.range` |
|---|---|---:|---:|---:|
| Sylvaris Rhovan Lockmere | Half-Elf | 60 | **0** | 5 |
| Darthoridan Pastina | High Elf | 60 | **0** | 5 |
| Tharok Zephyrblaze | Dragonborn | 0 | 0 | 5 |
| Torden Lynn | Standard Human | 0 | 0 | 5 |
| Tyrus Quickwit | Standard Human | 0 | 0 | 5 |
| Berrit "Bolzen" Hawkin | Variant Human | 0 | 0 | 6.2 |

The race Items are attached but carry **0 Active Effects**, so nothing downstream
supplies the sense either. `visionMode` is hardcoded to `"basic"` at `actors.py:330`.

## Defect 2 — senses are emitted at the path dnd5e deprecated in 5.3

The converter emits the flat shape:

```python
senses = {"darkvision": 0, "blindsight": 0, ...}
```

dnd5e 5.3.3 declares senses as a mapping under `ranges`
(`module/data/shared/senses-field.mjs`):

```js
fields = {
  ranges: new MappingField(
    new NumberField({ required: true, nullable: true, integer: true, min: 0, initial: null }),
    { initialKeys: CONFIG.DND5E.senses, initialKeysOnly: true }
  ),
  units: ..., special: ...
}
```

`SensesField._migrate()` relocates the flat keys into `ranges` on load and
`_shim()` keeps the old accessor alive, so output still works today — while
logging:

```
senses.darkvision has moved to "senses.ranges.darkvision".
Deprecated since Version DnD5e 5.3
Backwards-compatible support will be removed in Version DnD5e 6.1
```

Under ADR-008 the converter emits 5.x natively and must not rely on a system
migration. This one is load-bearing: when the shim goes in 6.1, **NPC** senses
break too, not just PC senses.

Note also that the schema's own `initial` is `null` ("no such sense"), whereas the
converter writes `0`.

## Suggested fix

1. Emit the 5.3 shape — `{"ranges": {...}, "units": "ft", "special": ""}` — and
   prefer `null` over `0` for an absent sense.
2. Lift the `isNPC()` gate so characters get senses too. For a PC the available
   Roll20 evidence is the token's configured night-vision distance, which the
   converter already computes as `dim_sight`/`bright_sight`; feed the same value
   into `senses.ranges.darkvision` rather than only into `sight.range`.
3. When compendium matching supplies a race Item, prefer the sense granted by that
   race over the token radius — a Half-Elf token whose Roll20 owner never
   configured night vision should still convert with darkvision 60.
4. Set `visionMode` from the resulting sense instead of the hardcoded `"basic"`.

## Regression tests

- A character actor with a Roll20 token night-vision radius of 60 converts to
  `system.attributes.senses.ranges.darkvision == 60`.
- A character actor converts with **no** flat `senses.darkvision` key present.
- An NPC whose `npc_senses` reads `darkvision 120 ft., passive Perception 16`
  converts to `ranges.darkvision == 120` and `special == ""`.
- Schema-diff: no emitted actor carries a top-level `senses.<sense>` key.

## Field result (2026-08-04, re-converted *Wardens of the North* on 1.7.0)

The schema half landed; the player-character half did not.

| Check | Result |
|---|---|
| senses use the `ranges` mapping | **394 / 394** |
| NPC darkvision still parsed | **215 of 371** NPCs |
| **character actors with darkvision > 0** | **0 of 23** |

Four of those characters carry a token `sight.range` of 35–80 ft and still
converted to `darkvision: 0`, so the derivation is not firing in the frozen build
despite `getCharacterDarkvision` being present in it and returning a value when
called in isolation. The cause has not been isolated; doing so needs an
instrumented build run against a real campaign.

**That investigation is worth less than it looks, because the derivation is
unsound anyway.** Roll20 records no senses for a player character, and the token
radius is not a substitute: Darthoridan Pastina is a **High Elf**, who should have
**60 ft** of darkvision, and his Roll20 token carries a **5 ft** radius. A working
derivation would have written 5 — a wrong value that looks configured, which is
worse than an obviously absent one.

The defensible source is the **race**, which the converter already matches to a
compendium Item. Until that is implemented, PC senses are a **post-conversion
repair step** and are documented as such in the pipeline (`R20_to_Foundry_Pipeline.md`,
§B6b).
