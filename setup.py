import sys
import cx_Freeze
from cx_Freeze import setup, Executable
from src.version import version

sys.path.append("src")
# Dependencies are automatically detected, but it might need
# fine tuning.
buildOptions = {
    "build_exe": {
        "packages": [],
        "includes": ["bottle_websocket", "numpy"],
        "excludes": ["PySide2", "PyQt5", "matplotlib.tests", "numpy.random._examples"],
        "include_files": [
            ("Changelog.md", "Changelog.md"),
            ("README.md", "README.md"),
            ("README.html", "README.html"),
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

base = None
if sys.platform == "win32":
    base = GUI_BASE
    buildOptions["build_exe"]["include_files"].append(("electron", "electron"))
    buildOptions["build_exe"]["includes"].append("tkinter")
    buildOptions["build_exe"]["excludes"].append("wx")
    buildOptions["build_exe"]["excludes"].append("numpy")
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
