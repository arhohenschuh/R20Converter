# ADR-004: Automated test suite and CI safety net

- **Status**: Accepted
- **Date**: 2026-07-25
- **Supersedes**: —
- **Superseded by**: —

## Context

R20Converter had roughly 9,400 lines of Python and **zero** automated tests. The
only file under `.github/` was `FUNDING.yml`, so nothing ran on push or pull
request. The largest modules are also the least approachable: `actors.py` is
~2,800 lines and `scenes.py` ~930.

The only way to validate a change was to run a full conversion against a real
Roll20 export and inspect the resulting world by hand in Foundry. Those exports
contain other people's copyrighted campaign material and cannot be committed as
fixtures, so that validation is neither shareable nor repeatable.

ADR-002 commits us to rewriting the document schema emitted by every one of
those files. Doing that without a safety net would be reckless.

## Decision

Introduce a `pytest` suite plus a GitHub Actions workflow, starting with the
logic that can be tested honestly today and growing alongside the ADR-002 port.

**Scope of the initial suite** — the pure, high-risk logic that needs no
campaign fixture:

- Asset path derivation (`urlsafe`, `getDestinationPaths`): collision handling,
  deduplication, `max_path` fallback, and output-directory containment. This is
  where untrusted names from the export become real filesystem paths.
- Asset downloading: the Roll20 resolution fallback chain, timeout propagation,
  caching, and error reporting — all against a stubbed session, never the
  network.
- The argparse interface, which is the project's actual public API and where
  three of the bugs this work fixed were hiding.
- `utils.getFVTTDataPath` and the shared user-facing messages.

**Testing conventions**:

- `tests/conftest.py` puts `src/` on `sys.path`, mirroring how the application
  runs (`python3 src/main.py`), because `src` is not an installable package and
  its modules import each other by bare name.
- Collaborators are replaced with small explicit fakes (`FakeDatabase`,
  `StubSession`) rather than mocking frameworks, so a test failure points at
  behaviour rather than at call bookkeeping.
- Tests never touch the network and never write outside `tmp_path`.
- Class-level caches such as `Entity.resource_cache` are reset by an autouse
  fixture; they are shared mutable state and leak between tests otherwise.

**Dependencies**: `requirements-dev.txt` holds a small, modern, unpinned-lower-
bound test set. It is deliberately separate from `requirements.txt`, which is
pinned to the frozen Windows build's Python 3.8 target (ADR-001) and drags in
cx_Freeze, eel, numpy and matplotlib that no test needs.

**CI** (`.github/workflows/ci.yml`) runs on every push and pull request:

- byte-compile every module under `src/`, which catches syntax errors in the
  many files no test imports yet;
- run the test suite on Python 3.11 and 3.12;
- lint and build the Vue front-end, which is otherwise only ever built manually
  on a release machine.

## Alternatives considered

- **Golden-file tests over a real campaign export.** Rejected: exports are
  copyrighted third-party material and frequently large. A synthetic minimal
  campaign fixture is a good future addition and would enable end-to-end
  coverage of `R20Converter.convert()`; it is a larger piece of work than this
  ADR takes on.
- **Testing via the pinned `requirements.txt`.** Rejected: those pins target
  Python 3.8, which is end-of-life and unavailable on current CI runners, and
  they include a heavy build toolchain irrelevant to the tests.
- **Adding a Python linter (flake8/ruff) now.** Deferred. The existing code has
  a large backlog of style findings; introducing a linter in the same change as
  behavioural fixes would bury them in noise. Worth doing as a dedicated,
  separately reviewable commit.

## Consequences

- Regressions in path handling, download behaviour and the CLI surface are
  caught automatically.
- The ADR-002 document schema port has a place to add characterisation tests
  before each document type is changed.
- Coverage is currently concentrated in helpers; the entity writers themselves
  remain untested until the port supplies both new behaviour and its tests.
- `requirements.txt` still pins `Pillow 10.4.0`, which has known advisories but
  cannot be raised without dropping the Python 3.8 build target. Modernising
  that target is its own decision and should get its own ADR.
