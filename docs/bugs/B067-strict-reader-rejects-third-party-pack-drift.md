# B067 - Strict reader rejects third-party pack drift

**Severity:** High
**Status:** Fixed in v1.14.0
**Found:** 2026-08-20 during frozen LMoP qualification

## Defect

v1.12.0 correctly made recursive output validation fail on missing or orphaned child records. The
same strict reader was also used for installed system and custom compendium inputs. Beyond5e
1.1.11's class pack contains ActiveEffect children omitted from parent indexes, so the entire pack
was discarded from enrichment. Its extraction also contains an empty stale `.db` directory beside
one real LevelDB pack, producing another false load attempt.

## Fix contract

- Packs R20Converter emits and reads back remain strict by default.
- External system/custom compendiums use explicit `strict=False` input recovery.
- Declared children keep parent order; unlisted children follow in stable ID order.
- Directories without a LevelDB `CURRENT` file are not treated as packs.

## Regression coverage

`tests/test_leveldb_pack.py` proves the same orphan graph is rejected in strict mode and recovered
in permissive mode. Output write/read gates remain unchanged.