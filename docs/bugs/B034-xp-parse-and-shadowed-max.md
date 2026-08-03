# B034: `createDetailXP` zeroes slash-format XP and shadows the `max` builtin

- **Status**: Fixed in 1.0.1 (F034)
- **Severity**: Minor (XP lost for "X/Y"-format sheets; pct silently never computed)
- **Found**: 2026-08-03 audit
- **Component**: `src/entities/actors.py:1076-1110`

## Defects

Two independent bugs in one function, both verified empirically:

1. **The parsed value is unconditionally discarded.**

   ```python
   except ValueError:
       if "/" in current:
           try:
               current = int(current.split("/")[0].replace(",", "").replace(".", ""))
           except:
               current = 0
       current = 0        # <-- runs regardless, wiping the value just parsed
   ```

   A sheet storing experience as `"3400/6500"` (or `"3,400"` — any non-plain-int)
   converts to `details.xp.value = 0`. Measured: `createDetailXP("3400/6500", …)`
   → `current = 0`.

2. **`max` is shadowed by an int, so `pct` always throws.** The tuple unpack
   `(current, max, _) = self.getAttribute(...)` and the later `max =
   max_per_level[level]` rebind `max` to an integer, so
   `percent = max(0, min(100, ...))` raises `TypeError: 'int' object is not
   callable`, which the bare `except` converts to `percent = 0`. Measured: the
   `TypeError` fires even for plain-int XP. (Consequence is limited: `pct` and
   `max`/`min` are derived in 5.x and dropped from `details.xp` on load anyway —
   but the code is dead weight pretending to work.)

## Suggested fix

Rename the local to `xp_max`, hoist the slash-parse into the happy path with an
explicit `else`, and emit only `{"value": current}` since 5.x derives the rest.
