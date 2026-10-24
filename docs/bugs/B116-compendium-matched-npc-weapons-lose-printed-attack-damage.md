# B116: Compendium-matched OGL NPC weapons lose the printed attack and damage

- Severity: High
- Status: Fixed in v1.16.2
- Observed release: R20Converter 1.16.1, commit cbb0d0e7a9665c43f780c26d3f31ef98f853454d
- Reported: 24 October 2026, Dragoncoast Danger played-world reconversion (`dcd/v130`)
- Related: B090, B100 (same "source-authored NPC component" principle, not yet applied to weapons)

## Reproduction

Convert the Dragoncoast Danger R20Exporter 1.5.3 archive (SHA-256 `0397FED9...4639D3`) with
`--custom-compendium` Beyond5e 1.6.60, `--custom-compendium-mode additive`,
`--custom-compendium-precedence custom`, and `--no-compendium-overwrite`, then migrate with
Foundry 14.369 / dnd5e 6.0.6 and read every NPC attack activity's runtime labels.

Of 150 attack-flagged OGL NPC actions with printed damage, 25 roll different damage (17%), and 13 of
the 27 affected actions also roll a different to-hit. Examples:

| NPC | Action | Printed (`attack_tohit`, `attack_onhit`) | Converted |
| --- | --- | --- | --- |
| Otyugh | Bite | +6, `2d8 + 3` piercing | +6, `1d6 + @mod` **slashing** |
| Borko (Minotaurus) | Greataxe | +6, `2d12 + 4` slashing | +6, `1d12 + 4` |
| Shegren | Light Crossbow | +3, `1d8 + 3` piercing plus `2d6` poison | +6, `1d8 + 3` (poison lost) |
| Cristan Prolovnir | Rapier | +6, `1d6 + 3` plus `7d6` poison | +6, `1d8 + 3` |
| Gerbos Pseudodragon | Bite | +4, `1d4 + 2` piercing | +0 (STR), `1d6 - 2` slashing |
| Raida "Twigs" | Shortsword | +7 (Martial Role: Attacker) | +5 |

## Cause

When an NPC action name matches a compendium weapon (`Bite`, `Shortsword`, `Greataxe`, …), the
item is created from the donor and `--no-compendium-overwrite` keeps the donor's damage dice,
damage type, and attack ability. The printed `attack_tohit`, `attack_damage`, `attack_damage2`, and
damage types of the statblock are discarded. `addNPCAction` computes a correct attack ability or
explicit bonus, but that result does not survive the compendium path. Sheets whose printed to-hit
already equals ability + proficiency hide the defect; damage dice differing from the donor and
extra damage parts do not.

## Expected Behavior

NPC actions remain source-authored, as B090/B100 require for other NPC components. The printed
to-hit, all damage parts, and damage types define the activity. A compendium donor may contribute
presentation only (image, description enrichment, weapon properties). It never changes attack
or damage mechanics.

## Regression Requirements

- Otyugh `Bite` (`2d8 + 3` piercing, +6) converts to exactly that attack and damage.
- An action with `attack_damage2` keeps both parts with their own types.
- A printed to-hit that no ability reproduces is carried as a flat bonus.
- The same structure under different NPC/module identities behaves identically.
- Control: an NPC action without a compendium match is unchanged.

## Downstream Disposition

Dragoncoast Danger 1.3.0-rc.1 restores the 27 affected actions post-conversion from the immutable
printed statblocks (rule R-ATK). Post-repair parity is 150/150 damage and 498 printed scalar
checks with 2 explicitly dispositioned differences.

## Generic Resolution

Source-authored NPC attacks bypass donor mechanics replacement. The converter retains the
computed printed to-hit and all source damage parts/types; a matching donor may supply artwork.
Ordinary PC inventory enrichment is unchanged. The decision is tied to the NPC action creation
path, not an actor/action/module name. Renamed matched/unmatched controls and bonus attacks are
covered by [test_asset_and_compendium_fixes.py](../../tests/test_asset_and_compendium_fixes.py).
