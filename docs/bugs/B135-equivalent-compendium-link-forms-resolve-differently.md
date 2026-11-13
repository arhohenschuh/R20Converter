# B135: Equivalent Roll20 compendium links resolve differently by host and trailing slash

- Severity: Moderate
- Status: Fixed in v1.17.1
- Observed release: R20Converter 1.17.0, commit eae5e7f
- Reported: 13 November 2026, Curse of Strahd 1.4.0 conversion intake D6
- Upstream copy filed by mistake: kakaroto/R20Converter#103
- Related: [B071](B071-prose-compendium-targets-remain-external.md), [B075](B075-missing-compendium-link-becomes-invalid-item-uuid.md)

## Report And Re-Diagnosis

The intake reported that links such as `Spells:Light/` create the stray world Items
`Light14IIIIIIIII` and `Darkvision14IIII`. The output contradicts that attribution:

- Both Items are Beyond5e donors, internalized because the links **without** a slash
  (`https://roll20.net/compendium/dnd5e/Spells:Light`) resolved. Internalizing executable donor
  targets is the B071 design for self-contained modules, not this defect.
- Links **with** a slash were never resolved. `Spells:Darkvision/#h-Darkvision` was looked up as
  `Darkvision/`, which logged `Could not find compendium item of type 'Spells' and name 'Darkvision/'`.
- Links on `app.roll20.net` were never matched at all and stayed raw Roll20 URLs.

So one Roll20 entry produced three different results depending only on its URL form.

## Source Census

*Curse of Strahd* 1.5.7 (SHA-256 `A0319692…ABCE`): 11 category links with a trailing slash
before the fragment (`Spells:Bless/`, `Darkvision/`, `Etherealness/`, `Light/`, `Shield/`) and 56
`app.roll20.net` links, 18 of them with a category. The three intake samples with HTML markup in
the path have no category; this resolver does not handle category-less links on any host, before
or after the fix.

## Resolution

`roll20.net`, `app.roll20.net` and `www.roll20.net` category links use one resolver. The
resolver drops the fragment and query, then a trailing slash, before the existing item and donor
lookup. Resolved links behave exactly as the equivalent `roll20.net` link already did.

Unresolved links keep their previous output. `roll20.net` links follow B075 (readable text in
modules, original link in worlds). `app.` and `www.` links, which earlier releases never rewrote,
remain byte-identical so downstream localization can still retarget them.

## Verification

`tests/test_document_schema.py`: four URL forms (slash plus fragment, alternate host, `%3A` with
query) resolve to the same Item in world and module exports; a donor lookup receives the bare name;
an unresolved `app.roll20.net` link is unchanged. The 1.17.0 source fails the nine resolution cases.

Unmodified Curse of Strahd export: raw trailing-slash category links fall from 9 to 0, and all 14
`app.roll20.net` Spells links resolve. The Items, Monsters, Rules and Backgrounds links on that host
are left as they were. Five more Beyond5e spells are internalized under B071: Augury, Bless,
Etherealness, Protection from Evil and Good, and Shield.

## Downstream Note

Retargeting spell links to campaign-local spell Journals and removing internalized donor Items is
module policy, kept in the post-conversion pipeline.
