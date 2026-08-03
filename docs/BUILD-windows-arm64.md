# Building and running on Windows ARM64

**Summary: the shipped build is x64 throughout and is expected to run on
Windows-on-ARM under emulation. There is no native ARM64 build, and producing
one is blocked upstream rather than by anything in this repository.**

## What ships today

Every binary in `build/exe.win-amd64-3.8` is x86-64:

| component | evidence | architecture |
| --- | --- | --- |
| build output | directory name `exe.win-amd64-3.8` | x64 |
| interpreter | `3.8.20 … [MSC v.1929 64 bit (AMD64)]` | x64 |
| LevelDB binding (ADR-009) | `plyvel_ci-1.5.1-cp38-cp38-win_amd64.whl` | x64 |
| its extension module | `_plyvel.cp38-win_amd64.pyd` | x64 |
| its vendored DLLs | `leveldb-*`, `snappy-*`, `msvcp140-*`, `vcruntime140_1-*` | x64 |
| GUI shell | Electron v43.2.0 `win32-x64` | x64 |

## Running the x64 build on ARM64

Expected to work under Windows 11's x64 emulation with no special steps.

The bundle being *uniformly* x64 is what makes that safe. Windows emulates a
whole process, and the failure mode on ARM64 is mixing arm64 and x64 modules
inside one process — an arm64 host trying to load an x64 `.pyd`, or the
reverse. Since the interpreter, the LevelDB extension and Electron are all x64,
the process is emulated end to end.

Expect it to be slower. The heaviest parts of a conversion are asset download
and image processing (Pillow), which is where emulation overhead lands.

> **Not verified on ARM64 hardware.** The architecture table was read off the
> build; the emulation behaviour is the documented platform contract, not a
> measurement taken here. Treat this as expected-to-work, not confirmed.

## Why there is no native ARM64 build

Three upstream blockers, in the order they have to be cleared:

1. **Python 3.8 has no Windows ARM64 distribution.** CPython added `win-arm64`
   as a supported target in 3.11. This is the hard blocker — nothing else can
   be attempted until the toolchain moves off 3.8, which `requirements.txt` and
   `setup.py` currently pin against.
2. **No ARM64 LevelDB wheel is in use.** The wheel this build installs is
   `win_amd64`. Whether `plyvel-ci` publishes a `win_arm64` variant for any
   interpreter has **not been checked** — if it does not, LevelDB and snappy
   have to be compiled for ARM64, which is exactly the "requires a C toolchain"
   objection ADR-003 raised. ADR-009 only escaped it because a prebuilt x64
   wheel existed.
3. **cx_Freeze must support the target.** Untested here. It follows whatever
   interpreter it runs under, so this largely resolves with (1).

Electron is not a blocker: it publishes `win32-arm64` builds, so `setup.py`'s
`include_files` entry only needs pointing at the ARM64 runtime.

## If you attempt it

The graceful path already exists. `src/leveldb_pack.py` imports `plyvel` inside
a `try`/`except`, so an ARM64 build **without** it still produces working
output: NeDB module packs that Foundry converts on import, and compendium
enrichment skipped with a warning naming the import error. That is the 1.1.0
behaviour, which was a usable release.

Rough order of work:

1. Move the pinned interpreter to 3.11+ and re-pin `requirements.txt`. Check
   `eel`, `bottle-websocket`, `numpy` and `Pillow` have ARM64 wheels at those
   versions.
2. Build once *without* plyvel and confirm the fallback produces a world. This
   separates "does the app build on ARM64" from "does LevelDB build".
3. Only then source or compile an ARM64 `plyvel`, and re-run the ADR-009
   verification: convert with `--export-as-module` and confirm `packs/` holds
   directories rather than `.db` files, with no "LevelDB support is
   unavailable" warning in the log.
4. Swap the Electron runtime for `win32-arm64` and smoke-test the GUI: the
   window must still be alive ~12s after launch, with an empty `stderr.log`.

## Note on the trade-off

Before 1.2.0 the converter was pure Python, and an ARM64 build would have
needed only an ARM64 interpreter. ADR-009 bought native LevelDB packs at the
cost of a compiled dependency, and ARM64 is where that cost shows up. The
fallback in `leveldb_pack` is what keeps it a degradation rather than a wall.
