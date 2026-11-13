# B132: A token whose Roll20 character was deleted aborts module assembly

- Severity: High
- Status: Fixed in v1.17.1
- Observed release: R20Converter 1.17.0, commit eae5e7f
- Reported: 13 November 2026, Curse of Strahd 1.4.0 conversion intake D3
  (`Curse of Strahd-1.5.7.zip`, SHA-256 `A0319692…ABCE`; also in the 1.0.0 export)
- Upstream copy filed by mistake: kakaroto/R20Converter#100

## Reproduction

Roll20 keeps a placed token after the character it `represents` is deleted. The reported export has
one: page *Town of Vallaki*, GM-layer token `-KmADi3x3v52UxF7FxaV` ("Guard"), `represents:
"-KgKKC8RJ3IY34mnYJTR"`, which matches no character in the campaign.

The Scene emitted the token with an `actorId` for that missing character. Module assembly then
rejected the Adventure after every document had been converted:

```text
broken token actor link NGVjOTU0NmM3ODMy
```

A world export kept the dangling `actorId` instead.

## Cause

Generic converter defect. The token constructor normalized `represents` without checking whether
an Actor exists. The assembly gate correctly refuses a dangling link, but it fires at the end of a
long run and gives no source location.

## Resolution

Actors are converted before Scenes. When a placed token represents a character for which no Actor
exists, the Scene warns with the token ID, name, page and missing character ID, and emits the token
with `actorId: null`. Placement, art, name and visibility are unchanged. No other Actor is
substituted: a same-name match is identity guessing and stays a module-specific repair. The
assembly gate remains as the final safety net.

## Verification

`tests/test_scene_exploration.py`: a token for a deleted character converts without an Actor and
warns, while a sibling token for an existing character keeps its link. The 1.17.0 source fails it.

The unmodified reported export now converts completely with the
[pipeline's c4 arguments](../../Changelog.md#v1171). Exactly one *Guard* token has no Actor, the
warning names `-KmADi3x3v52UxF7FxaV`, there are no broken token links in the Scene pack, and the
Adventure carries the same token. The downstream repoint to the existing *Guard* Actor remains a
campaign decision.
