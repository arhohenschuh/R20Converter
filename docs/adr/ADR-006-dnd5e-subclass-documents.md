# ADR-006: Emit dnd5e subclasses as documents, not a string field

* Status: Accepted
* Date: 2026-07-26
* Supersedes: none
* Related: [ADR-002](ADR-002-target-foundry-v13.md)

## Context

`src/entities/items.py` wrote a character's subclass into the class item as a
plain string:

```json
{ "type": "class", "system": { "levels": 10, "subclass": "School of Evocation" } }
```

That field has not existed since **dnd5e 2.1**, which promoted the subclass to
its own Item document. A subclass is now bound to its class by matching
identifiers:

```json
{ "type": "class",    "system": { "identifier": "wizard" } }
{ "type": "subclass", "system": { "classIdentifier": "wizard",
                                  "identifier": "school-of-evocation" } }
```

The failure mode is silent. Foundry's `DataModel` discards unknown keys without
warning, so `system.subclass` is dropped on import and the sheet shows an empty
"Add Subclass" slot. Nothing is logged, and re-writing the field appears to
succeed — a repair script can report "9 subclasses set" on every run and never
change anything, because the value never lands.

This is not cosmetic. The subclass carries the character's archetype features,
and on a converted sheet the class is the only place that information existed.

Two constraints shaped the fix.

**Subclass identity is a content decision, not a data transformation.** Roll20's
OGL sheet stores the subclass as a free-text string (`"Tempest Domain"`,
`"The Hexblade"`). Resolving that to a specific compendium document requires
knowing which rules content the destination world has installed, and name
matching across third-party packs is unreliable — the same name appears in
multiple packs with different mechanics, and the SRD ships only one subclass per
class. The converter also routinely runs with no local Foundry installation at
all (see `README.md`), so there may be no compendium to consult.

**`DEFAULT_SYSTEM_VERSION` is load-bearing.** `src/foundry.py` declares `1.5.6`
and `entities/settings.py` writes it to `dnd5e.systemMigrationVersion`. That
makes dnd5e replay its whole migration chain from 1.5.6 on first world launch,
which is what converts this converter's pre-4.0 item shapes (`system.damage.parts`,
`system.actionType`) into the Activities model dnd5e 4.0+ requires. It looks
like a stale constant; it is not, and this ADR does not change it.

## Decision

Emit the documents dnd5e actually reads.

* `ItemClass` writes `identifier` — the class name slugified — and no longer
  writes `subclass`.
* A new `Item.createItemSubclass()` produces a `subclass` document carrying
  `identifier` and the `classIdentifier` of its parent class.
* `Actor.createItemClass()` emits that companion document whenever Roll20
  supplied a subclass name, for the base class and for each multiclass entry.

Identifiers are produced with `python-slugify`, already a hard dependency
(`requirements.txt`), matching Foundry's `String#slugify({strict: true})`:
`"School of Evocation"` → `"school-of-evocation"`.

**The subclass is emitted verbatim, with no compendium lookup.** The document
carries the Roll20 name and an empty description. Linking it to real rules
content is left to the GM, who knows which books the table uses.

## Consequences

* Subclasses survive conversion and appear on the sheet, correctly bound to
  their class. Multiclassed characters get one subclass document per class.
* The emitted subclass has a name but no features. This is deliberate: the
  alternative is guessing, and a wrong guess is worse than an obvious blank,
  because it silently attaches mechanics the character never had.
* Output is **not** backwards compatible with dnd5e below 2.1, consistent with
  ADR-002. A world on dnd5e 1.x sees an unknown item type.
* The emitted subclass passes through dnd5e's migration chain from 1.5.6, since
  `systemMigrationVersion` is unchanged. Those migrations reshape legacy fields;
  on a document already in the modern shape they are no-ops, and the fields this
  ADR writes (`identifier`, `classIdentifier`) are not touched by any of them.
* `Items.createItemClass()` and `Item.createItemClass()` lose their `subclass`
  parameter. Both are internal to this project; `Actor.createItemClass()` keeps
  its signature so the Roll20-facing call sites are unchanged.

## Alternatives considered

**Resolve the subclass against installed compendiums.** Rejected. It only works
when Foundry is installed locally, and name matching is ambiguous across packs —
the same subclass name resolves to different mechanics depending on pack order.
Emitting the wrong subclass is harder to detect than emitting a blank one.

**Keep writing `system.subclass` as well, for older dnd5e.** Rejected. ADR-002
already commits to a single modern target, and the field is inert — it would be
dead weight that implies a compatibility guarantee this project does not make.

**Leave it and document the gap.** Rejected. The data is present in the Roll20
export and cheap to emit correctly; losing it silently is the worst outcome.
