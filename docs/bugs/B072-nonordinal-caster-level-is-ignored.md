# B072 - Non-ordinal caster level is ignored

**Severity:** High
**Status:** Fixed in v1.14.0
**Found:** 2026-08-20 during frozen LMoP qualification

`getNPCCasterLevel()` accepted `4th-level spellcaster` and `4th level spellcaster`, but Roll20 also
emits `4-level spellcaster`. The unmatched trait produced caster level zero, so a module NPC with
ordinary spells and no printed slot attributes had no initialized capacity.

The parser now makes the ordinal suffix optional while retaining the required `level spellcaster`
phrase. Regression coverage includes the observed `4-level` form and existing ordinal forms.