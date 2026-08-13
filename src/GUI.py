import os
import io
import sys
import eel
import json
import socket
import inspect
import zipfile
import subprocess
import platform
from slugify import slugify
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr
from R20Converter import R20Converter

if platform.system() == 'Darwin':
    import wx
    useWx = True
else:
    from tkinter import Tk
    from tkinter.filedialog import askopenfilename, askdirectory
    useWx = False

from utils import getFVTTDataPath
from version import version
import messages


def _resourceDir():
    """Directory holding the bundled resources (``client/dist``, ``electron``).

    A frozen build puts them next to the executable. Running from source they
    live in the working directory the application is documented to be started
    from. Resolving them explicitly means the app no longer only works when the
    current directory happens to be the right one.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.getcwd()


# eel resolves its web root through ``sys._MEIPASS`` whenever ``sys.frozen`` is
# set, but ``_MEIPASS`` is a PyInstaller attribute and this application is
# packaged with cx_Freeze, which sets ``sys.frozen`` without it. Without this
# shim ``eel.init()`` raises AttributeError, importing this module fails, and
# the executable silently falls back to parsing command line arguments -- which
# looks to the user like double-clicking the program does nothing at all.
if getattr(sys, "frozen", False) and not hasattr(sys, "_MEIPASS"):
    sys._MEIPASS = _resourceDir()

# eel 0.14 replaced the ``custom_callback`` hook, which handed the browser
# launch back to the caller, with a plain ``cmdline_args`` list.
_EEL_HAS_CUSTOM_CALLBACK = "custom_callback" in inspect.signature(eel.start).parameters


def _findFreePort():
    sock = socket.socket()
    try:
        sock.bind(("localhost", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


class GUIClass:
    def __init__(self):
        path = os.path.join(_resourceDir(), "client", "dist")
        if not os.path.exists(path):
            path = "client/dist"
        eel.init(path)
        self.campaign = None
        self.loadedPath = None

    def logInfo(self, msg):
        eel.logInfo(msg)() # pylint: disable=no-member
    def logWarning(self, msg):
        eel.logWarning(msg)() # pylint: disable=no-member
    def logError(self, msg):
        eel.logError(msg)() # pylint: disable=no-member

    def start(self):
        # On windows and mac, use bundled electron
        if platform.system() in ['Windows', 'Darwin']:
            if _EEL_HAS_CUSTOM_CALLBACK:
                return eel.start('index.html', port=0, mode="custom",
                                 custom_callback=self.PopenElectron)
            # In "custom" mode current eel versions run cmdline_args verbatim
            # and never append the page URL, so the port cannot be left as 0.
            command = self.electronCommandLine()
            if command is not None:
                port = _findFreePort()
                url = "http://localhost:%d/index.html" % port
                return eel.start('index.html', port=port, mode="custom",
                                 cmdline_args=command + [url])
            # No bundled Electron: fall back to the user's browser rather than
            # failing back into command line mode.
            return eel.start('index.html', port=0, mode="default")

        # On linux, try chrome then default
        try:
            eel.start('index.html', port=0, mode="chrome")
        except:
            eel.start('index.html', port=0, mode="default")

    def electronCommandLine(self):
        """Command that launches the bundled Electron shell, or None."""
        if platform.system() == 'Darwin':
            path = os.path.join(_resourceDir(), "Electron.app")
            if not os.path.exists(path):
                path = os.path.join(os.path.dirname(os.path.dirname(sys.executable)),
                                    "Resources", "Electron.app")
            if not os.path.exists(path):
                return None
            return ["open", "-a", path, "--args"]
        for name in ("electron.exe", "electron"):
            path = os.path.join(_resourceDir(), "electron", name)
            if os.path.exists(path):
                return [path]
        return None

    def PopenElectron(self, args, urls):
        cmd = self.electronCommandLine()
        if cmd is None:
            raise RuntimeError("Could not find the bundled Electron application")
        cmd = cmd + args + [';'.join(urls)]
        return subprocess.Popen(cmd)

    def loadCampaign(self, file_type, path):
        if path == self.loadedPath:
            return
        if file_type == "JSON":
            with open(path, "r", encoding='utf-8') as f:
                self.campaign = json.load(f)
        else:
            zip = zipfile.ZipFile(path, "r")
            self.campaign = json.load(zip.open("campaign.json".replace(os.path.sep, "/")))
        self.loadedPath = path


GUI = GUIClass()

@eel.expose
def getVersion():
    return version


@eel.expose
def ask_file():
    """ Ask the user to select a file """
    if useWx:
        app = wx.App(None)
        dialog = wx.FileDialog(None, 'Browse Campaign', wildcard="Campaign File(*.json; *.zip)|*.json;*.zip", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        app.SetTopWindow(dialog)
        style = dialog.GetWindowStyle()
        dialog.SetWindowStyle(style | wx.STAY_ON_TOP)
        if platform.system() == 'Darwin':
            os.system('''/usr/bin/osascript -e 'tell app "Finder" to set frontmost of process "R20Converter-{}" to true' '''.format(version))
        if dialog.ShowModal() == wx.ID_OK:
            path = dialog.GetPath()
        else:
            path = None
        dialog.Destroy()
    else:
        root = Tk()
        root.wm_attributes('-topmost', 1)
        root.withdraw()
        file_path = askopenfilename(parent=root)
        path = None if file_path == "" else file_path
    return path

@eel.expose
def ask_scene_folders():
    """Ask for an optional scene-folder JSON manifest."""
    if useWx:
        app = wx.App(None)
        dialog = wx.FileDialog(None, 'Browse Scene Folder Manifest',
                               wildcard="JSON File (*.json)|*.json",
                               style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        app.SetTopWindow(dialog)
        style = dialog.GetWindowStyle()
        dialog.SetWindowStyle(style | wx.STAY_ON_TOP)
        if platform.system() == 'Darwin':
            os.system('''/usr/bin/osascript -e 'tell app "Finder" to set frontmost of process "R20Converter-{}" to true' '''.format(version))
        path = dialog.GetPath() if dialog.ShowModal() == wx.ID_OK else None
        dialog.Destroy()
    else:
        root = Tk()
        root.wm_attributes('-topmost', 1)
        root.withdraw()
        file_path = askopenfilename(parent=root,
                                    title="Browse Scene Folder Manifest",
                                    filetypes=(("JSON File", "*.json"),))
        path = None if file_path == "" else file_path
    return path

@eel.expose
def ask_folder():
    """ Ask the user to select a folder """
    if useWx:
        app = wx.App(None)
        dialog = wx.DirDialog(None, 'Browse folder', "", style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)
        app.SetTopWindow(dialog)
        style = dialog.GetWindowStyle()
        dialog.SetWindowStyle(style | wx.STAY_ON_TOP)
        if platform.system() == 'Darwin':
            os.system('''/usr/bin/osascript -e 'tell app "Finder" to set frontmost of process "R20Converter-{}" to true' '''.format(version))
        if dialog.ShowModal() == wx.ID_OK:
            path = dialog.GetPath()
        else:
            path = None
        dialog.Destroy()
    else:
        root = Tk()
        root.wm_attributes('-topmost', 1)
        root.withdraw()
        folder = askdirectory(parent=root)            
        root.update()
        path = None if folder == "" else folder
    return path

@eel.expose
def does_file_exist(file_path):
    """ Checks if a file exists """
    return os.path.isfile(file_path)


@eel.expose
def does_folder_exist(path):
    """ Checks if a folder exists """
    return os.path.isdir(path)

@eel.expose
def loadCampaign(file_type, path):
    try:
        GUI.loadCampaign(file_type, path)
        return None
    except Exception as e:
        return str(e)
@eel.expose
def getCampaignTitle(file_type, path):
    try:
        GUI.loadCampaign(file_type, path)
        title = GUI.campaign["campaign_title"]
        return title
    except:
        return None
@eel.expose
def getCampaignSlug(file_type, path):
    title = getCampaignTitle(file_type, path)
    if title:
        return slugify(title)
    return None

@eel.expose
def getFoundryDirectory():
    path = getFVTTDataPath()
    return path if os.path.isdir(path) else None

@eel.expose
def slugifyString(name):
    return slugify(name)

class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self

@eel.expose
def startConversion(args):
    error = None
    try:
        converter = R20Converter(AttrDict(args), logger=GUI)
        converter.convert()
    except Exception as e:
        try:
            import traceback
            error = traceback.format_exc()
        except:
            error = str(e)
        GUI.logError(e)

    if error:
        message = messages.conversionErrorMessage(version, error)
    else:
        message = messages.conversionSuccessMessage(html=True)
    GUI.logInfo(message)
    return {
        "error": error is not None,
        "message": message
    }
