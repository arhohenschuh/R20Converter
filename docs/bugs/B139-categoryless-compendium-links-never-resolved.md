# B139: Category-less Roll20 compendium links are never resolved

- Severity: Moderate
- Status: Fixed in v1.17.2
- Observed release: R20Converter 1.17.1, commit ec39f13
- Reported: 13 November 2026, Waterdeep: Dragon Heist 1.3.0 conversion intake E2
- Related: [B071](B071-prose-compendium-targets-remain-external.md), [B075](B075-missing-compendium-link-becomes-invalid-item-uuid.md), [B135](B135-equivalent-compendium-link-forms-resolve-differently.md)

## Report And Re-Diagnosis

The intake attributed the unresolved links to their `#fragment` (`#content`, `#h-...`). The
source census contradicts that. In the Dragon Heist 1.3.0 export, all 75 `Category:Name` links
that carry a fragment resolve normally, because the resolver already strips fragments. Every
unresolved dnd5e link uses Roll20's current URL form, which names the entry **without a
category**:

| Link form (`roll20.net/compendium/dnd5e/...`) | Dragon Heist 1.3.0 | Curse of Strahd 1.5.7 |
| --- | --: | --: |
| `Category:Name`, e.g. `Spells:Detect%20Magic` (with or without fragment) | 189 | 22 |
| `Detect%20Magic` (category-less) | 34 | 500 |
| empty target (`compendium/dnd5e/`) | 7 | 0 |

The resolver only parsed `Category:Name`, so category-less links stayed Roll20 URLs. That held
even when the same spell had been internalized from a category link elsewhere.

## Resolution

Category-less links on `roll20.net`, `app.roll20.net` and `www.roll20.net` are resolved after the
category pass. The fragment, query and trailing slash are dropped. An existing source Item with
that name wins, as for category links. Otherwise the entry is resolved only when **exactly one** of
the supported lookup types (Spells, Items) has that name, and then exactly as the equivalent
category link would be (B071 internalization in modules, a world Item in worlds). A name found
both as a spell and an item (for example *Shield*), an unknown name, an empty target, HTML markup
in the path, and other Roll20 books (`compendium/monstermanual/...`) leave the link unchanged.
Category-less links are not retried as category-less.

Both link forms now end the URL at the quote that opened the `href`. Roll20 writes names such as
`Mordenkainen's Magnificent Mansion` with a literal apostrophe inside a double-quoted URL, and the
earlier pattern accepted either quote as the closing one. That cut the name at the apostrophe,
for category links as well.

## Verification

`tests/test_document_schema.py`: four category-less forms (fragment, alternate host, trailing
slash, query) resolve to the only matching spell; an existing source Item takes precedence;
unknown and ambiguous names, empty targets, markup and other books stay unchanged without
warnings; an unresolved category link is looked up only once; apostrophes inside double-quoted
category and category-less URLs, and a single-quoted control, resolve. The 1.17.1 source fails the
eight fix cases.

Unmodified Dragon Heist 1.3.0 export, against the pipeline's 1.17.1 output: raw category-less
links fall from 27 to 0, and the only remaining raw dnd5e links are the 7 empty-target source
artefacts. Journal Item links rise from 173 to 202, and eight more Beyond5e entries are
internalized under B071. Pages, Walls, Tokens and Actors are unchanged.

Unmodified Curse of Strahd 1.5.7 export, against the v1.17.1 source build: raw category-less links
fall from 497 to 38, and Journal Item links rise from 18 to 477. The remaining 38 name NPCs and
monsters, book-only items, a background, markup artefacts, or *Antipathy Sympathy* (Beyond5e:
*Antipathy/Sympathy*), none of which is a unique spell or item. 142 Beyond5e entries are
internalized. The 21 new Actors are the summon profiles their activities reference, closed by B071.
Pages, Walls and Tokens are unchanged. Modules gain those Items and their icons; downstream
retargeting to campaign-local Journals remains module policy.
