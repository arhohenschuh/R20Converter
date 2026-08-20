# B065 - Module output is not self-contained

**Severity:** High
**Status:** Fixed in v1.14.0
**Found:** 2026-08-20 while moving generic post-conversion assembly upstream

## Defect

Module export wrote individual entity packs and a manifest, but no Adventure document. A GM had to
import packs separately, risking regenerated IDs and broken placed Token links. External images in
HTML and document fields remained owned by Roll20 or another module. Executable compendium UUIDs
could point to Actors or Items unavailable where the converted module was installed.

The converter also rewrote every Roll20 Journal link to a same-module UUID without checking that
the source export contained the target. Sunless Citadel's Potion of Healing therefore referenced a
Journal ID that did not exist in any pack.

## Fix contract

- Emit one native Adventure with stable source IDs, all source pack populations, and pack folders.
- Reject duplicate/missing folder parents and broken placed Token actor links.
- Internalize document and embedded HTML art through the existing safe asset pipeline.
- Clone resolvable external executable Actor/Item targets locally and rewrite their UUIDs.
- Reject malformed or unresolved executable references; declare remaining external prose links as
  recommended modules.
- Preserve readable labels for source links whose targets are absent.
- Keep campaign-authored tables, encounter policy, and editorial additions downstream.

## Regression coverage

`tests/test_module_assembly.py` covers Adventure ID/folder conservation, broken Token links,
Item-typed deck cards, executable-target cloning/rejection, and embedded image ownership.
`tests/test_document_schema.py` covers valid and absent Roll20 links. The v1.14.0 shipping suite
passes 872 tests. A full Sunless module passes Gate A 32/0/0/7 and an independent reader proves
exact Adventure/source populations, 146/146 Token links, and zero external HTML images.

Final frozen LMoP qualification passes Gate A 36/0/0/3 and exact Adventure/source conservation
for 40 Actors, 119 Items, 10 Scenes, 87 Journals, 13 Tables, 22 folders, and 206/206 Token actor
links. Published LMoP 1.5.3 remains the release of record; this conversion is disposable converter
evidence only.