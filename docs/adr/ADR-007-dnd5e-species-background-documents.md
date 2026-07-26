# ADR-007: Emit dnd5e species and backgrounds as documents, not string fields

* Status: Accepted
* Date: 2026-07-26
* Supersedes: none
* Related: [ADR-002](ADR-002-target-foundry-v13.md), [ADR-006](ADR-006-dnd5e-subclass-documents.md)

## Context

`src/entities/actors.py` writes a character's species and background into the
actor as plain strings:

```json
{ "type": "character",
  "system": { "details": { "race": "Half-Elf", "background": "Spy (Smuggler)" } } }
```

**dnd5e 4.0** promoted both to Item documents, the same move ADR-006 records for
the subclass in 2.1. The sheet reads embedded documents of type `race` and
`background`. (The 2024 rules renamed the concept to *Species* in the interface,
but the document type is still `race`.)

`system.details.race` and `system.details.background` did not become dead fields.
They changed meaning: they now hold the **`_id` of the embedded document**, and
dnd5e maintains them itself through document hooks —

```js
// module/data/item/race.mjs
_onCreate(data, options, userId) {
  this.parent.actor.update({ "system.details.race": this.parent.id });
}
_preDelete(options, user) {
  await this.parent.actor.update({ "system.details.race": null });
}
```

`background.mjs` does the same. **Those hooks never fire for this converter.**
They run when a document is created through Foundry's document API at runtime;
R20Converter writes NeDB JSON directly, so nothing invokes them. The converter
has to write the link itself, or it emits a document the actor does not point at.

The failure mode is identical to ADR-006 and just as quiet. Foundry's `DataModel`
discards what it does not recognise without warning, so nothing is logged and the
character sheet simply offers empty **"Add Species"** and **"Add Background"**
slots. A GM has no indication the campaign ever carried that information.

This was confirmed against a real conversion rather than inferred. Of 394 actors,
23 are `character`-typed and 6 are genuine player characters; the embedded item
types across all of them are:

```
spell 281 · loot 156 · feat 123 · weapon 59 · class 24 · equipment 17
```

Zero `race` documents and zero `background` documents, while every one of the six
PCs carries both values as strings — `Half-Elf` / `Spy (Smuggler)`,
`Dragonborn` / `Mercenary Veteran`, `Variant Human` / `Mercenary Veteran`, and so
on. The data survives conversion intact and is discarded at import.

Three constraints shape the fix.

**Identity is a content decision, not a data transformation.** Roll20's OGL sheet
stores both as free text. Turning the string `"Half-Elf"` into a document means
choosing *which* Half-Elf, from which source, with which traits — a judgement
about the table's rules content, not a reshaping of data. This is why dnd5e's own
migration correctly declines to do it rather than guessing.

**The SRD cannot supply most of these anyway.** SRD 5.1 ships exactly **one**
background, Acolyte. None of the six backgrounds in the sample exist in it.
Species fare better but still do not match verbatim: `Standard Human` and
`Variant Human` are not SRD entries, and `High Elf` is a subrace of `Elf`. A
lookup strategy would resolve a minority of cases and mislead on the rest.

**`DEFAULT_SYSTEM_VERSION` remains load-bearing.** As ADR-006 records, `1.5.6` in
`src/foundry.py` is written to `dnd5e.systemMigrationVersion` so dnd5e replays its
migration chain and converts this project's pre-4.0 item shapes into the
Activities model. This ADR does not change it.

## Decision

Emit the documents dnd5e actually reads, following ADR-006 exactly.

* New `Item.createItemRace()` and `Item.createItemBackground()` produce `race`
  and `background` documents carrying the Roll20 name and an `identifier`
  derived with the existing `identifierFor()` helper from ADR-006.
  `identifier` is not decorative: `ItemDescriptionTemplate` — mixed into every
  item type, including these two — declares it
  `new IdentifierField({ required: true })`.
* `Actor` emits each document when Roll20 supplied a non-empty value, alongside
  the class and subclass documents it already produces.
* **`system.details.race` and `system.details.background` are set to the `_id`
  of the document just emitted**, replacing the Roll20 name that used to sit
  there. Writing the name would leave the actor pointing at nothing.
* `system.details.originalClass` is set to the `_id` of the character's first
  class document. dnd5e stores the primary class there and normally assigns it
  in `ClassData._onCreate` via `actor._assignPrimaryClass()` — another hook that
  does not fire for a raw import. The converter previously wrote `""`.

**Empty values emit nothing.** A value that is missing or whitespace-only
produces no document and leaves the link field falsy. This is not a theoretical
guard: in a sample conversion, 15 of 23 `character`-typed actors are Roll20 area
templates ("20ft. radius", "10ft. cone") carrying neither value. Emitting for
them would add 30 documents named `""` to the world.

**Both are emitted verbatim, with no compendium lookup.** Each document carries
the Roll20 name and an empty description. Linking them to real rules content is
left to the GM, who knows which books the table uses. This is the same call
ADR-006 made, for the same reason, and the SRD's single background makes the
argument stronger here than it was there.

## Consequences

* Species and background survive conversion and appear on the sheet. The empty
  "Add Species" / "Add Background" slots on every converted PC go away.
* The emitted documents have a name but no mechanical features. This is
  deliberate, for the reason ADR-006 gives: a wrong guess is worse than an
  obvious blank, because it silently attaches traits the character never had.
* The post-import repair macro's species/background pass becomes unnecessary for
  newly converted worlds. It remains useful for worlds already imported.
* Output is **not** backwards compatible with dnd5e below 4.0, consistent with
  ADR-002 and ADR-006. An older world sees unknown item types.
* Values that a GM will want to relink by hand are now visible *as documents* on
  the sheet rather than invisible, which is what makes the manual step discoverable.
* This closes the last known instance of the promotion pattern. Class was always
  a document, subclass was fixed in ADR-006, species and background are fixed
  here. Any future dnd5e release that promotes another field will reproduce the
  same silent loss, and the same remedy applies.

## Alternatives considered

**Resolve against installed compendiums.** Rejected, more firmly than in ADR-006.
SRD 5.1 contains one background, so the strategy fails for five of six sampled
values before pack ambiguity is even considered. It also only works when Foundry
is installed locally, and the converter routinely runs without it.

**Normalise subraces to their base race** (`High Elf` → `Elf`). Rejected. It
discards the specificity the campaign recorded in order to hit an SRD entry the
character may not have been built from. If a GM wants the SRD document they can
drag it in; the converter should not silently downgrade the data.

**Leave it to the post-import macro.** Rejected. The macro fixes one world after
the fact; the converter fixes every conversion at the source. The values are
present in the export and cost nothing to emit — losing them silently, once per
conversion, forever, is the outcome ADR-006 already rejected.

**Also drop the legacy `details` strings.** Rejected on the original draft of
this ADR, then reversed during review. The premise was wrong: those fields are
not legacy at all, they are the link to the embedded document. Keeping the
Roll20 name in them would leave a dangling reference — worse than either
alternative, and invisible until a GM wondered why the sheet ignored a species
that plainly exists in the item list.
