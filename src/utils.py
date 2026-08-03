import os
import platform
import json


def _optionsDataPath(path):
    """``dataPath`` from a Foundry install's ``Config/options.json``."""
    try:
        with open(os.path.join(path, "Config", "options.json"), "r", encoding='utf-8') as f:
            return json.load(f).get("dataPath") or None
    except Exception:
        return None


def isFVTTDataPath(path):
    """Whether ``path`` is a Foundry user-data directory we can read.

    ``Data/systems`` is the part the converter actually needs: without it there
    is no system manifest and no compendium enrichment.
    """
    return bool(path) and os.path.isdir(os.path.join(path, "Data", "systems"))


def resolveFVTTDataPath(path):
    """Resolve a supplied path to a usable data directory, or ``None``.

    Accepts either the data directory itself or an installation directory
    holding ``Config/options.json``. A portable install keeps its config beside
    the application and its data somewhere else entirely, and the installation
    folder is the path a user actually knows.
    """
    if not path:
        return None
    path = os.path.expanduser(path)
    if isFVTTDataPath(path):
        return path
    configured = _optionsDataPath(path)
    if configured and isFVTTDataPath(configured):
        return configured
    return None


def fvttDataPathCandidates():
    """Places a Foundry data directory or installation may live, in order."""
    candidates = []
    environment = os.environ.get("FOUNDRY_VTT_DATA_PATH", None)
    if environment:
        candidates.append(environment)
    system = platform.system()
    if system == "Windows":
        local = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
        candidates.append(os.path.join(local, "FoundryVTT"))
    elif system == "Darwin":
        candidates.append(os.path.join(os.path.expanduser("~/Library/Application Support"),
                                       "FoundryVTT"))
    else:
        candidates.append(os.path.join(os.environ.get("XDG_DATA_HOME",
                                                      os.path.expanduser("~/.local/share")),
                                       "FoundryVTT"))
        candidates.append(os.path.join(os.path.expanduser("~"), "FoundryVTT"))
        candidates.append(os.path.join("/local", "FoundryVTT"))
    return candidates


def getFVTTDataPath():
    """Best guess at the Foundry user-data directory.

    Each candidate is checked for ``Data/systems`` rather than taken on trust.
    A stale ``options.json`` -- one naming a path from another machine, or a
    default install pointing at itself while the real data lives with a portable
    copy -- used to be accepted silently, and the conversion then ran with no
    compendium enrichment and no explanation.

    Returns the first usable candidate, else the first candidate so the caller
    still has something to name in its error.
    """
    for candidate in fvttDataPathCandidates():
        resolved = resolveFVTTDataPath(candidate)
        if resolved:
            return resolved
    candidates = fvttDataPathCandidates()
    return candidates[0] if candidates else None

def logInfo(msg):
    print(msg)
def logWarning(msg):
    print(msg)
def logError(msg):
    print(msg)