import os
import sys
import cx_Freeze
from cx_Freeze import setup, Executable
from src.version import version

sys.path.append("src")
# Dependencies are automatically detected, but it might need
# fine tuning.
try:
    import plyvel  # noqa: F401
    _HAS_PLYVEL = True
except ImportError:
    _HAS_PLYVEL = False

buildOptions = {
    "build_exe": {
        "packages": [],
        # plyvel is a native extension writing LevelDB compendium packs
        # (ADR-009). cx_Freeze does not detect it: `leveldb_pack` imports it
        # inside a try/except so a source install can run without it. Only
        # force-include it when it is actually installed (e.g. missing on
        # win-arm64, which has no plyvel-ci wheel).
        "includes": ["bottle_websocket", "numpy"] + (["plyvel"] if _HAS_PLYVEL else []),
        "excludes": ["PySide2", "PyQt5", "matplotlib.tests", "numpy.random._examples"],
        "include_files": [
            ("Changelog.md", "Changelog.md"),
            ("README.md", "README.md"),
            ("README.html", "README.html"),
            ("Advanced.md", "Advanced.md"),
            ("templates", "templates"),
            ("client/dist", "client/dist")
        ]
    },
    "bdist_mac": {
        "iconfile": "client/public/logo.icns"
    },
    "bdist_dmg": {
        "volume_label": "R20Converter-{}".format(version),
        "applications_shortcut": True
    }
}
                
# GUI applications require a different base on Windows (the default is for a
# console application). cx_Freeze 8 renamed the Windows GUI base from
# "Win32GUI" to "gui"; the old name now raises rather than being accepted as an
# alias, and the pinned 7.2.10 cannot install on Python 3.12+ because its `lief`
# pin has no wheel there. Support both so the build works on either.
GUI_BASE = "gui" if int(cx_Freeze.__version__.split(".")[0]) >= 8 else "Win32GUI"


def _plyvelLibraries():
    """The DLL directory the plyvel wheel ships beside its package.

    ``plyvel-ci`` is repaired by delvewheel: ``_plyvel.pyd`` links against
    mangled ``leveldb-*.dll`` / ``msvcp140-*.dll`` names that live in a sibling
    ``plyvel_ci.libs`` directory, and its import hook looks for that directory
    at ``../plyvel_ci.libs``. cx_Freeze copies the package but not the sibling,
    so the extension builds fine and then fails to load (ADR-009).
    """
    try:
        import plyvel
    except Exception:
        return None
    package = os.path.dirname(os.path.abspath(plyvel.__file__))
    libraries = os.path.join(os.path.dirname(package), "plyvel_ci.libs")
    return libraries if os.path.isdir(libraries) else None


base = None
if sys.platform == "win32":
    base = GUI_BASE
    buildOptions["build_exe"]["include_files"].append(("electron", "electron"))
    buildOptions["build_exe"]["includes"].append("tkinter")
    buildOptions["build_exe"]["excludes"].append("wx")
    buildOptions["build_exe"]["excludes"].append("numpy")
    _libraries = _plyvelLibraries()
    if _libraries:
        buildOptions["build_exe"]["include_files"].append(
            (_libraries, "lib/plyvel_ci.libs"))
if sys.platform == "darwin":
    buildOptions["build_exe"]["includes"].append("wx")
    buildOptions["build_exe"]["excludes"].append("tkinter")

executables = [
    Executable('src/main.py', base=base, target_name = 'R20Converter', icon = "client/public/logo.ico")
]

if sys.platform == "win32":
    # A second, console-based entry point over the same code. The GUI build has
    # no stdout, so `main.py` redirects it to stdout.log — which makes the CLI
    # unusable interactively: no progress, no errors, and a non-zero exit is
    # invisible. This target is the one to script against.
    executables.append(
        Executable('src/main.py', base=None, target_name='R20Converter-cli',
                   icon="client/public/logo.ico")
    )

setup(name='R20Converter',
      version = version,
      description = 'Convert a Roll 20 Campaign into a Foundry VTT world',
      options = buildOptions,
      executables = executables
      )
