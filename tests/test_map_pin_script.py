import json
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "templates" / "map-pin-notes.js"


def test_map_pin_script_is_click_only_and_opens_the_slugged_heading():
    harness = r"""
const fs = require("fs");
const vm = require("vm");

const callbacks = new Map();
let nextHookId = 1;
global.Hooks = {
  once(name, callback) {
    if (name === "init") callback();
  },
  on(name, callback) {
    const id = nextHookId++;
    callbacks.set(id, {name, callback});
    return id;
  },
  off(name, id) {
    callbacks.delete(id);
  },
  callAll(name, ...args) {
    for (const hook of callbacks.values()) {
      if (hook.name === name) hook.callback(...args);
    }
  },
};

const calls = {
  click: 0,
  activate: 0,
  hoverIn: 0,
  hoverOut: 0,
  canHover: 0,
  canViewUser: null,
  isVisible: 0,
};
class Note {
  get isVisible() {
    calls.isVisible += 1;
    return true;
  }

  _onClickLeft() {
    calls.click += 1;
  }

  _onClickLeft2() {
    calls.activate += 1;
    const options = {};
    Hooks.callAll("activateNote", this, options);
    calls.anchors ??= [];
    calls.anchors.push(options.anchor);
  }

  _canControl() {
    return false;
  }

  _onHoverIn() {
    calls.hoverIn += 1;
  }

  _onHoverOut() {
    calls.hoverOut += 1;
  }

  _canHover() {
    calls.canHover += 1;
    return true;
  }

  _canView(user) {
    calls.canViewUser = user;
    return true;
  }
}

global.CONFIG = {Note: {objectClass: Note}};
global.game = {user: {isGM: false, id: "player"}};
global.JournalEntryPage = {
  implementation: {
    slugifyHeading(heading) {
      calls.slugified = heading;
      return "38-secret-tunnel";
    },
  },
};

vm.runInThisContext(fs.readFileSync(process.argv[1], "utf8"), {filename: process.argv[1]});

function makeNote(pin, page = null) {
  const note = {
    document: {
      page,
      getFlag(scope, key) {
        return scope === "R20Converter" && key === "mapPin" ? pin : null;
      },
    },
  };
  Object.setPrototypeOf(note, Note.prototype);
  return note;
}

const page = {
  toc: {
    "source-authored-anchor": {
      text: "38. Secret Tunnel",
      slug: "source-authored-anchor",
    },
  },
};
const mapPin = makeNote({subLink: "38. Secret Tunnel", visibleTo: "all"}, page);
mapPin._onHoverIn({});
mapPin._onHoverOut({});
mapPin._onClickLeft({});
mapPin._onClickLeft({});
mapPin._onClickLeft2({});
const canView = mapPin._canView();
const canHover = mapPin._canHover();
const visibleToPlayer = mapPin.isVisible;

const fallbackPin = makeNote({subLink: "40. Fallback Heading", visibleTo: "all"});
fallbackPin._onClickLeft({});
fallbackPin._onClickLeft2({});

const hiddenPin = makeNote({subLink: "39. Hidden Room", visibleTo: ""});
const hiddenCanView = hiddenPin._canView();
const hiddenVisibleToPlayer = hiddenPin.isVisible;
game.user = {isGM: true, id: "gm"};
const hiddenVisibleToGM = hiddenPin.isVisible;

const ordinaryNote = makeNote(null);
ordinaryNote._onHoverIn({});
ordinaryNote._onHoverOut({});
const ordinaryCanHover = ordinaryNote._canHover();
const ordinaryVisible = ordinaryNote.isVisible;

process.stdout.write(JSON.stringify({
  calls,
  canView,
  canHover,
  visibleToPlayer,
  hiddenCanView,
  hiddenVisibleToPlayer,
  hiddenVisibleToGM,
  ordinaryCanHover,
  ordinaryVisible,
  remainingHooks: callbacks.size,
}));
"""

    result = subprocess.run(
        ["node", "-e", harness, str(SCRIPT)],
        check=True,
        capture_output=True,
        text=True,
    )
    observed = json.loads(result.stdout)

    assert observed == {
        "calls": {
            "click": 0,
            "activate": 2,
            "hoverIn": 1,
            "hoverOut": 1,
            "canHover": 2,
            "canViewUser": {"isGM": False, "id": "player"},
            "isVisible": 3,
            "slugified": "40. Fallback Heading",
            "anchors": ["source-authored-anchor", "38-secret-tunnel"],
        },
        "canView": True,
          "canHover": True,
          "visibleToPlayer": True,
          "hiddenCanView": False,
          "hiddenVisibleToPlayer": False,
          "hiddenVisibleToGM": True,
          "ordinaryCanHover": True,
          "ordinaryVisible": True,
        "remainingHooks": 0,
    }


def test_map_pin_script_is_reachable_through_foundry_interaction_permissions():
    harness = r"""
const fs = require("fs");
const vm = require("vm");

const hooks = new Map();
global.Hooks = {
  once(name, callback) {
    if (name === "init") callback();
  },
  on(name, callback) {
    hooks.set(1, {name, callback});
    return 1;
  },
  off(name, id) {
    hooks.delete(id);
  },
  callAll(name, ...args) {
    for (const hook of hooks.values()) {
      if (hook.name === name) hook.callback(...args);
    }
  },
};

let now = 1000;
Date.now = () => now;
const calls = {activate: 0, control: 0, hoverIn: 0, hoverOut: 0};
class Note {
  get isVisible() {
    return true;
  }

  _canControl() {
    return this.nativeControlAllowed;
  }

  _canHover() {
    return true;
  }

  _canView() {
    return true;
  }

  _onClickLeft() {
    calls.control += 1;
  }

  _onClickLeft2() {
    calls.activate += 1;
    Hooks.callAll("activateNote", this, {});
  }

  _onHoverIn() {
    calls.hoverIn += 1;
  }

  _onHoverOut() {
    calls.hoverOut += 1;
  }
}

global.CONFIG = {Note: {objectClass: Note}};
global.game = {user: {isGM: false, id: "player"}};
global.JournalEntryPage = {implementation: {slugifyHeading: () => "area-key"}};
vm.runInThisContext(fs.readFileSync(process.argv[1], "utf8"), {filename: process.argv[1]});

function makePin({visibleTo = "all", nativeControlAllowed = false} = {}) {
  const note = {
    nativeControlAllowed,
    document: {
      page: null,
      getFlag(scope, key) {
        return scope === "R20Converter" && key === "mapPin"
          ? {subLink: "Area Key", visibleTo}
          : null;
      },
    },
  };
  Object.setPrototypeOf(note, Note.prototype);
  return note;
}

function interaction(note) {
  const permissions = {
    hoverIn: note._canHover,
    clickLeft: note._canControl,
    clickLeft2: note._canView,
  };
  const callbacks = {
    hoverIn: note._onHoverIn,
    hoverOut: note._onHoverOut,
    clickLeft: note._onClickLeft,
    clickLeft2: note._onClickLeft2,
  };
  return {
    can(action) {
      return permissions[action].call(note, game.user, {});
    },
    callback(action) {
      return callbacks[action].call(note, {}) ?? true;
    },
  };
}

const playerPin = makePin();
const playerInteraction = interaction(playerPin);
const playerHoverAllowed = playerInteraction.can("hoverIn");
const playerHoverAccepted = playerInteraction.callback("hoverIn") !== false;
const playerSingleAllowed = playerInteraction.can("clickLeft");
if (playerSingleAllowed) playerInteraction.callback("clickLeft");
const playerDoubleAllowed = playerInteraction.can("clickLeft2");
if (playerDoubleAllowed) playerInteraction.callback("clickLeft2");
const playerHoverOutAccepted = playerInteraction.callback("hoverOut") !== false;

const hiddenPin = makePin({visibleTo: ""});
const hiddenInteraction = interaction(hiddenPin);
const hiddenSingleAllowed = hiddenInteraction.can("clickLeft");
const hiddenDoubleAllowed = hiddenInteraction.can("clickLeft2");

now += 1000;
game.user = {isGM: true, id: "gm"};
const gmPin = makePin({visibleTo: "", nativeControlAllowed: true});
const gmInteraction = interaction(gmPin);
const gmSingleAllowed = gmInteraction.can("clickLeft");
if (gmSingleAllowed) gmInteraction.callback("clickLeft");

const ordinaryNote = {
  nativeControlAllowed: true,
  document: {getFlag() { return null; }},
};
Object.setPrototypeOf(ordinaryNote, Note.prototype);
const ordinaryInteraction = interaction(ordinaryNote);
const ordinaryControlAllowed = ordinaryInteraction.can("clickLeft");
const ordinaryHoverAllowed = ordinaryInteraction.can("hoverIn");
const ordinaryViewAllowed = ordinaryInteraction.can("clickLeft2");

process.stdout.write(JSON.stringify({
  calls,
  playerHoverAllowed,
  playerHoverAccepted,
  playerSingleAllowed,
  playerDoubleAllowed,
  playerHoverOutAccepted,
  hiddenSingleAllowed,
  hiddenDoubleAllowed,
  gmSingleAllowed,
  ordinaryControlAllowed,
  ordinaryHoverAllowed,
  ordinaryViewAllowed,
  remainingHooks: hooks.size,
}));
"""

    result = subprocess.run(
        ["node", "-e", harness, str(SCRIPT)],
        check=True,
        capture_output=True,
        text=True,
    )
    observed = json.loads(result.stdout)

    assert observed == {
        "calls": {"activate": 2, "control": 1, "hoverIn": 0, "hoverOut": 0},
        "playerHoverAllowed": True,
        "playerHoverAccepted": True,
        "playerSingleAllowed": True,
        "playerDoubleAllowed": True,
        "playerHoverOutAccepted": True,
        "hiddenSingleAllowed": False,
        "hiddenDoubleAllowed": False,
        "gmSingleAllowed": True,
        "ordinaryControlAllowed": True,
        "ordinaryHoverAllowed": True,
        "ordinaryViewAllowed": True,
        "remainingHooks": 0,
    }