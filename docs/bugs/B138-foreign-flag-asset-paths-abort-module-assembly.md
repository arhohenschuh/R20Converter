# B138: Asset paths in another package's flags abort module assembly

- Severity: High
- Status: Fixed in v1.17.2
- Observed release: R20Converter 1.17.1, commit ec39f13 (internalization since v1.14.0, B065)
- Reported: 13 November 2026, Waterdeep: Dragon Heist 1.3.0 conversion intake E1
- Related: [B065](B065-module-output-not-self-contained.md)

## Reproduction

Beyond5e 2014 donor Actors carry Tokenizer's layer recipe in
`flags.tokenizer-2.layerStack[].src` and `.masks[].src`, for example
`modules/tokenizer-2/img/dark-texture.webp`. When a conversion internalizes such a donor, for
example a spell summon or familiar, and the converter data root has no `tokenizer-2` module,
module assembly stops:

```text
could not internalize module asset modules/tokenizer-2/img/dark-texture.webp
```

The pipeline reached a complete conversion only after copying 153 Tokenizer images into its data
root. It then stripped the flags and the 13 images the converter had copied into the module.

## Cause

Generic converter defect. B065 internalizes every external `modules/...` asset string anywhere in
a document, including other packages' flag namespaces. Those namespaces are private data:
Foundry and the game system never render them. So an unrendered recipe could abort the run, and
the output depended on whether an unrelated module happened to be installed in the data root.

Not a Beyond5e defect: Beyond5e's manifest records these paths as Tokenizer's re-edit recipe
that no Foundry surface renders. It deliberately does not require `tokenizer-2`.

## Resolution

Asset internalization skips flag namespaces that belong to other packages. It still processes
`core`, the game system's namespace, the converter's `R20Converter` namespace and the module's own
namespace, and every non-flag field. Paths in skipped namespaces stay exactly as authored, whether
or not their package is installed. One info line reports the count per namespace. A missing
rendered asset (portrait, token, icon, HTML image) or a missing asset in a processed flag namespace
still fails closed.

## Verification

`tests/test_module_assembly.py`: foreign flag paths, including prototype-token flags, stay
unchanged without aborting while rendered and system-flag assets are copied. Installed foreign
assets are not copied either. Missing portrait, own-flag and system-flag assets still abort. The
1.17.1 source fails the two fix cases.

The unmodified Dragon Heist 1.3.0 export converts completely with the pipeline's arguments and a
data root without `tokenizer-2`, where 1.17.1 aborted. The log reports `monsterMunch 68,
tokenizer-2 100` paths left unchanged. Against the pipeline's 1.17.1 output (c3, Tokenizer
installed), the module's `assets/external` lacks exactly the 13 Tokenizer images the pipeline
had stripped by hand, and the Actor set is identical.
