# B038: Shaped-sheet custom skills still emit the pre-5.x shape, with two internal math bugs

- **Status**: Fixed in 1.0.2 (F038)
- **Severity**: Minor (Shaped sheet only; B022 fixed the standard branch, this branch was missed)
- **Found**: 2026-08-03 audit
- **Component**: `src/entities/actors.py:1208-1276` (`createActorSkills`, `self._shaped` branch)

## Defects

1. **Legacy shape.** The Shaped repeating-skill branch emits
   `{value, ability, bonus, mod, passive}` — the very shape B022/F022 removed
   from the standard branch. In 5.x, `bonus`/`mod`/`passive` are not in the
   skill schema (`mod` and `passive` are derived; bonuses are the
   `bonuses.{check,passive}` `FormulaField`s) and the entry lacks `roll`. The
   sheet-derived flat bonus is therefore dropped for every Shaped actor.
2. **`passive = mod = getAttributeInt("passive", ...)`** (line 1256) chains the
   assignment, so `mod` is overwritten with the *passive* value (e.g. `12`
   instead of `+2`) before being emitted. Harmless only because 5.x drops the
   key — the emitted number is wrong.
3. **Bonus sign is inverted** relative to the fixed branch:
   line 1254 computes `bonus = (base_mod + prof * value) - mod`, while the
   standard branch (line 1162) computes `mod - (base_mod + prof * value)`.
4. **Non-standard keys are dropped wholesale.** A custom Shaped skill whose name
   is not one of the 18 standard keys is written into `skills.<lowercased name>`;
   the 5.x `skills` field only accepts configured keys, so the entry vanishes
   on load with no warning.

## Suggested fix

Route the Shaped branch through the same 5.x emission the standard branch uses
(`value`, `ability`, `bonuses.check/passive` formulas, `roll`), fix the sign and
the chained assignment, and surface custom skills that have no dnd5e key (log +
biography note) instead of silently emitting a key the schema deletes.
