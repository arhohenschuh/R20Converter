# B074 - Cloned donor Token name visibility drifts

**Severity:** Minor
**Status:** Fixed in v1.14.0
**Found:** 2026-08-20 during frozen LMoP qualification

Actors cloned from a custom compendium to close executable references retained the donor's
`prototypeToken.displayName`. Native converted Actors use Always for Owner (`40`), so localized
summons could hide their names from owners or expose them more broadly than the module policy.

Cloned Actor prototypes now set `displayName: 40` before entering the local Actor pack and
Adventure. The donor document remains unchanged.