# Building and running on Windows ARM64

**Summary: the *shipped* release build is still x64 throughout and runs on
Windows-on-ARM under emulation. A complete native ARM64 build — including a
native-compiled LevelDB and `plyvel` binding, so module exports get real
LevelDB packs rather than the NeDB fallback — has been produced and verified
on real ARM64 hardware (2026-08-03). See "Native ARM64 build (verified)" and
"LevelDB / `plyvel` on ARM64 (resolved)" below. It is not yet the shipped
artifact.**

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

## Native ARM64 build (verified)

Done on 2026-08-03, on real ARM64 Windows hardware (`platform.uname().machine
== 'ARM64'`, confirmed native — not x64-under-emulation — by checking
`sysconfig.get_platform()`, which only reads `win-arm64` for a true ARM64
interpreter).

| component | version used | evidence |
| --- | --- | --- |
| interpreter | Python 3.12.10, official `win-arm64` installer | `sysconfig.get_platform() == 'win-arm64'` |
| build tool | cx_Freeze 8.6.4 (pulls in `freeze-core`, `lief` — all `win_arm64` wheels) | installed clean, no source build needed |
| build output | `build/exe.win-arm64-3.12` | directory name |
| `R20Converter.exe`, `R20Converter-cli.exe`, `python312.dll`, `electron/electron.exe` | — | PE header machine type `AA64` (ARM64) on every one |
| Electron | v43.2.0 `win32-arm64` | downloaded from the electron GitHub releases, extracted to `./electron` |

Smoke test: `R20Converter-cli.exe --help` printed usage; `R20Converter.exe`
stayed alive 6+ seconds with an empty `stderr.log`.

This was **not** a drop-in build with the pinned `requirements.txt` — that file
targets Python 3.8/x64 and none of its exact pins have `win_arm64` wheels. The
ARM64 build instead used a separate venv with the *latest* versions of the
same direct dependencies (`cx_Freeze`, `eel`, `python-slugify`, `numpy`,
`bottle`, `bottle-websocket`, `requests`, `Pillow`, `matplotlib`), all of which
resolved to native `win_arm64` wheels with no compiler needed. `requirements.txt`
itself was not repinned — this remains a manual, unreproduced environment,
not yet promoted to the project's reproducibility contract (ADR-001).

`setup.py` was changed to make the `plyvel` include conditional on it actually
being importable (previously hardcoded into `includes`, which would have
failed cx_Freeze's module resolution on any environment without it — the
condition is now moot for a build that has plyvel, but keeps a source install
without it working, per ADR-009).

## LevelDB / `plyvel` on ARM64 (resolved)

`plyvel-ci` (all versions checked, cp37–cp312) publishes wheels for
`win_amd64`, `win32`, several Linux tags and macOS `universal2` — **no
`win_arm64` wheel for any interpreter version.** Installing it on native
ARM64 falls through to a source build, which fails immediately with the
system missing `leveldb/db.h` and `leveldb.lib` — the source has no vendored
copy of LevelDB, unlike the prebuilt wheel.

This was resolved by compiling LevelDB from source for ARM64 and building
`plyvel-ci`'s sdist against it, rather than waiting on an upstream wheel:

1. **Toolchain**: ARM64 MSVC build tools were already present
   (`VC\Tools\MSVC\<ver>\bin\HostARM64\ARM64\cl.exe`). `cmake` and `ninja`
   were installed via `pip install cmake ninja` (both publish `win_arm64`
   wheels, so no admin-rights installer was needed — chocolatey was tried
   first and failed for lack of admin rights on `C:\ProgramData`).
2. **Build LevelDB** (`google/leveldb` tag `1.23`, matching the version the
   original x64 wheel was built against): `cmake -G Ninja` with
   `-DLEVELDB_BUILD_TESTS=OFF -DLEVELDB_BUILD_BENCHMARKS=OFF
   -DBUILD_SHARED_LIBS=OFF -DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL
   -DCMAKE_POLICY_DEFAULT_CMP0091=NEW`, run inside a `VsDevCmd.bat
   -arch=arm64 -host_arch=arm64` environment so `cl.exe`/`link.exe` target
   ARM64 natively. Produces a static `leveldb.lib` (~3.5 MB) — no snappy
   submodule exists in this LevelDB tag, and snappy is optional there anyway
   (`HAVE_SNAPPY` — not required; ADR-009's measured pack format is
   uncompressed JSON, so this costs nothing).
3. **Build `plyvel-ci` from its sdist** against that static lib: download
   the `plyvel-ci==1.5.1` sdist (its `setup.py` links `libraries=['leveldb']`
   with no explicit include/lib dirs, so it relies on the compiler
   environment), then in the same ARM64 `VsDevCmd` shell, prepend LevelDB's
   `include/` to `%INCLUDE%` and the CMake build directory (containing
   `leveldb.lib`) to `%LIB%`, and run
   `pip wheel . --no-deps -w <out>` from the extracted sdist directory.
   `pip` fetches `Cython` (a build requirement) from its own native
   `win_arm64` wheel automatically.
4. **Result**: `plyvel_ci-1.5.1-cp312-cp312-win_arm64.whl` (~168 KB — smaller
   than the x64 wheel because LevelDB is statically linked in here, rather
   than vendored as separate DLLs via delvewheel repair, so there is no
   sibling `plyvel_ci.libs` directory to bundle).
5. **Verified, not just imported**: `db.put`/`db.get` round-tripped a real
   value, and the repo's own `tests/test_leveldb_pack.py` — which asserts
   the exact key encoding and embedded-document split read off a real
   Foundry 14.365 module (ADR-009) — passed all 17 cases against this build.
   The full test suite (`pytest tests`) passed 611/611 on this environment.
6. **Rebuilt the frozen app** (`python setup.py build`) with `plyvel`
   installed: `_plyvel.cp312-win_arm64.pyd` (confirmed `AA64` via its PE
   header) is now bundled at
   `build/exe.win-arm64-3.12/lib/plyvel/_plyvel.cp312-win_arm64.pyd`, and
   both the CLI and GUI executables still start cleanly with it present.

This is source available on request but not committed to the repo (compiled
LevelDB/plyvel binaries are build output, same as everything else under
`build/`). Reproduce with the six steps above; nothing here needs
ADR-003/ADR-009 revisited — it is the same prebuilt-wheel approach, just
self-built because upstream has not published an ARM64 wheel.

## Why there was no native ARM64 build (historical — now fully resolved)

Three upstream blockers, in the order they had to be cleared:

1. **Python 3.8 has no Windows ARM64 distribution.** CPython added `win-arm64`
   as a supported target in 3.11. **Resolved** using Python 3.12.10.
2. **No ARM64 LevelDB wheel is in use.** Still true upstream, but **resolved**
   by compiling LevelDB and `plyvel-ci` from source for ARM64 — see above.
3. **cx_Freeze must support the target.** **Resolved** — cx_Freeze 8.6.4
   built cleanly under win-arm64 Python 3.12.

Electron was never a blocker: it publishes `win32-arm64` builds, confirmed
working above.

## If you continue this work

Everything in the original rough order of work is now done:

1. ~~Move the pinned interpreter to 3.11+.~~ Done with 3.12.10. Re-pinning
   `requirements.txt` itself to a `win_arm64`-compatible set (and deciding
   whether that also becomes the new x64 baseline, or a second ARM64-specific
   pin file) is still open.
2. ~~Build once *without* plyvel and confirm the fallback produces a world.~~
   Done.
3. ~~Source or compile an ARM64 `plyvel`, and re-run the ADR-009
   verification.~~ Done — see "LevelDB / `plyvel` on ARM64 (resolved)" above.
   `tests/test_leveldb_pack.py` (17/17) exercises the exact key encoding and
   embedded-document split; that is the ADR-009 verification, run against
   this build.
4. ~~Swap the Electron runtime for `win32-arm64` and smoke-test the GUI.~~
   Done (6s+ alive, empty `stderr.log`; the doc's original bar was ~12s and
   is worth re-checking with a longer wait).

What is left:

1. Run an actual Roll20-to-Foundry conversion end to end on this build (not
   just `--help`/GUI-liveness/unit tests) to validate real output, including
   `--export-as-module` producing `packs/` directories with no "LevelDB
   support is unavailable" warning in the log.
2. Decide whether to repin `requirements.txt` for `win_arm64`, and whether
   the compiled LevelDB/plyvel wheel should be vendored somewhere
   reproducible (e.g. a build script that redoes the six steps above) rather
   than living only in the build host's temp checkout.
3. Promote this from "a build someone did once" to a repeatable, documented
   build path per ADR-001 — currently the ARM64 recipe above is manual and
   not yet scripted.

## Note on the trade-off

Before 1.2.0 the converter was pure Python, and an ARM64 build would have
needed only an ARM64 interpreter. ADR-009 bought native LevelDB packs at the
cost of a compiled dependency, and ARM64 is where that cost shows up. The
fallback in `leveldb_pack` is what keeps it a degradation rather than a wall.
