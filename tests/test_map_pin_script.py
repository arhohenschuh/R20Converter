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
      flags: pin ? {R20Converter: {mapPin: pin}} : {},
      getFlag() { throw new Error("Map Pin runtime must not validate the legacy flag scope"); },
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
  const pin = {subLink: "Area Key", visibleTo};
  const note = {
    nativeControlAllowed,
    document: {
      page: null,
      flags: {R20Converter: {mapPin: pin}},
      getFlag() { throw new Error("Map Pin runtime must not validate the legacy flag scope"); },
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
  document: {
    flags: {},
    getFlag() { throw new Error("Map Pin runtime must not call getFlag for ordinary Notes"); },
  },
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


def test_map_pin_script_resolves_visibility_inherited_by_configured_note_class():
    harness = r"""
const fs = require("fs");
const vm = require("vm");

global.Hooks = {
  once(name, callback) {
    if (name === "init") callback();
  },
  on() { return 1; },
  off() {},
};

class CoreNote {
  get isVisible() {
    return true;
  }
}

class ConfiguredNote extends CoreNote {
  _canControl() { return true; }
  _canView() { return true; }
  _onClickLeft() {}
  _onClickLeft2() {}
  _onHoverIn() {}
  _onHoverOut() {}
}

global.CONFIG = {Note: {objectClass: ConfiguredNote}};
global.game = {user: {isGM: false}};
global.JournalEntryPage = {implementation: {slugifyHeading: () => "heading"}};
vm.runInThisContext(fs.readFileSync(process.argv[1], "utf8"), {filename: process.argv[1]});

const makeNote = pin => {
  const note = {document: {
    flags: pin ? {R20Converter: {mapPin: pin}} : {},
    getFlag() { throw new Error("Map Pin runtime must not validate the legacy flag scope"); },
  }};
  Object.setPrototypeOf(note, ConfiguredNote.prototype);
  return note;
};
const ordinary = makeNote(null);
const hidden = makeNote({visibleTo: ""});
const player = {ordinary: ordinary.isVisible, hidden: hidden.isVisible};
game.user = {isGM: true};
const gm = {hidden: hidden.isVisible};

process.stdout.write(JSON.stringify({
  patched: ConfiguredNote.prototype.__r20MapPinClickPatched,
  ownsVisibility: Object.hasOwn(ConfiguredNote.prototype, "isVisible"),
  player,
  gm,
}));
"""

    result = subprocess.run(
        ["node", "-e", harness, str(SCRIPT)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == {
        "patched": True,
        "ownsVisibility": True,
        "player": {"ordinary": True, "hidden": False},
        "gm": {"hidden": True},
    }


def test_map_pin_script_layers_below_tokens_and_has_gm_edit_mode():
    harness = r"""
const fs = require("fs");
const vm = require("vm");

const hooks = new Map();
global.Hooks = {
  once(name, callback) {
    if (name === "init") callback();
    else this.on(name, callback);
  },
  on(name, callback) {
    const callbacks = hooks.get(name) || [];
    callbacks.push(callback);
    hooks.set(name, callbacks);
    return callbacks.length;
  },
  off() {},
  callAll(name, ...args) {
    return (hooks.get(name) || []).map(callback => callback(...args));
  },
};

class Container {
  constructor() {
    this.children = [];
    this.parent = null;
    this.destroyed = false;
    this.visible = true;
    this.zIndex = 0;
  }

  addChild(child) {
    child.parent?.removeChild(child);
    this.children.push(child);
    child.parent = this;
    return child;
  }

  removeChild(child) {
    const index = this.children.indexOf(child);
    if (index >= 0) this.children.splice(index, 1);
    child.parent = null;
    return child;
  }

  sortChildren() {
    this.children.sort((left, right) => left.zIndex - right.zIndex);
  }

  destroy() {
    this.destroyed = true;
  }
}

class BasePlaceablesLayer {
  get placeables() {
    return this.objects.children;
  }
}

class NotesLayer extends BasePlaceablesLayer {
  constructor() {
    super();
    this.objects = new Container();
    this.objects.visible = true;
    this.quadtree = {
      updates: 0,
      removals: 0,
      update() { this.updates += 1; },
      remove() { this.removals += 1; },
    };
    this.active = false;
  }

  activate() {
    this.active = true;
  }
}

const calls = {click: 0, activate: 0, hoverIn: 0, hoverOut: 0, releases: 0};
class Note {
  get isVisible() { return true; }
  get layer() { return canvas.notes; }
  get bounds() { return {x: this.document.x, y: this.document.y, width: 40, height: 40}; }
  get isPreview() { return false; }
  _canControl() { return true; }
  _canView() { return true; }
  _onClickLeft() { calls.click += 1; }
  _onClickLeft2() { calls.activate += 1; }
  _onHoverIn() { calls.hoverIn += 1; }
  _onHoverOut() { calls.hoverOut += 1; }
  _updateQuadtree() { calls.originalQuadtree = (calls.originalQuadtree || 0) + 1; }
  release() { this.controlled = false; calls.releases += 1; }
}

global.PIXI = {Container};
global.CONFIG = {
  Note: {objectClass: Note},
  Canvas: {layers: {notes: {layerClass: NotesLayer}}},
};
global.game = {
  user: {isGM: true, id: "gm"},
  scenes: {
    sortingMode: "a",
    toggleSortingMode() { this.sortingMode = "m"; calls.sortToggles = (calls.sortToggles || 0) + 1; },
  },
};
global.JournalEntryPage = {implementation: {slugifyHeading: () => "heading"}};

const notes = new NotesLayer();
const ticker = {
  callbacks: new Set(),
  add(callback) { this.callbacks.add(callback); },
  remove(callback) { this.callbacks.delete(callback); },
};
const interfaceLayer = new Container();
const documents = [];
global.canvas = {
  notes,
  tokens: {zIndex: 200},
  interface: interfaceLayer,
  app: {ticker},
  scene: {
    notes: documents,
    async updateEmbeddedDocuments(type, updates) {
      calls.updateType = type;
      calls.updates = updates;
      for (const update of updates) {
        const document = documents.find(candidate => candidate.id === update._id);
        document.locked = update.locked;
      }
    },
  },
};
global.ui = {
  controls: {render() { calls.controlsRendered = (calls.controlsRendered || 0) + 1; }},
  scenes: {render() { calls.scenesRendered = (calls.scenesRendered || 0) + 1; }},
};

function makeNote(id, pin) {
  const document = {
    id,
    x: 100,
    y: 200,
    locked: Boolean(pin),
    flags: pin ? {R20Converter: {mapPin: {subLink: "Area", visibleTo: ""}}} : {},
    getFlag() { throw new Error("Map Pin runtime must not call getFlag"); },
  };
  const note = {
    id,
    document,
    destroyed: false,
    controlled: false,
    renderFlags: {set() {}},
  };
  Object.setPrototypeOf(note, Note.prototype);
  document.object = note;
  documents.push(document);
  notes.objects.addChild(note);
  return note;
}

const pin = makeNote("pin", true);
const ordinary = makeNote("ordinary", false);
vm.runInThisContext(fs.readFileSync(process.argv[1], "utf8"), {filename: process.argv[1]});

Hooks.callAll("ready");
Hooks.callAll("canvasReady");
const previewParent = new Container();
previewParent.name = "NativeNotePreview";
const preview = makeNote("preview", true);
documents.pop();
notes.objects.removeChild(preview);
previewParent.addChild(preview);
Object.defineProperty(preview, "isPreview", {value: true});
Hooks.callAll("drawNote", preview);
const lowered = {
  parentName: pin.parent.name,
  zIndex: pin.parent.zIndex,
  ordinaryStayedNative: ordinary.parent === notes.objects,
  registeredIds: notes.placeables.map(note => note.id).sort(),
  quadtreeUpdates: notes.quadtree.updates,
  tickerCallbacks: ticker.callbacks.size,
  previewStayedNative: preview.parent === previewParent,
  previewRegistered: notes.placeables.includes(preview),
};

const gmControls = {notes: {tools: {}}};
Hooks.callAll("getSceneControlButtons", gmControls);
const tool = gmControls.notes.tools.r20MapPinEdit;
(async () => {
  await tool.onChange(null, true);
  pin.controlled = true;
  pin._onHoverIn({});
  pin._onHoverOut({});
  pin._onClickLeft({});
  const unlocked = {
    locked: pin.document.locked,
    notesActive: notes.active,
    toolVisible: tool.visible,
    updateType: calls.updateType,
    updates: calls.updates,
    calls: {...calls},
  };

  await tool.onChange(null, false);
  pin._onClickLeft({});
  const relocked = {
    locked: pin.document.locked,
    controlled: pin.controlled,
    calls: {...calls},
  };

  game.user = {isGM: false, id: "player"};
  const playerControls = {notes: {tools: {}}};
  Hooks.callAll("getSceneControlButtons", playerControls);
  Hooks.callAll("canvasTearDown");
  process.stdout.write(JSON.stringify({
    sorting: {mode: game.scenes.sortingMode, toggles: calls.sortToggles, renders: calls.scenesRendered},
    lowered,
    unlocked,
    relocked,
    playerHasTool: Object.hasOwn(playerControls.notes.tools, "r20MapPinEdit"),
    teardown: {
      pinRestored: pin.parent === notes.objects,
      registeredIds: notes.placeables.map(note => note.id).sort(),
      tickerCallbacks: ticker.callbacks.size,
    },
  }));
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
"""

    result = subprocess.run(
        ["node", "-e", harness, str(SCRIPT)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == {
        "sorting": {"mode": "m", "toggles": 1, "renders": 1},
        "lowered": {
            "parentName": "R20ConverterMapPins",
            "zIndex": 199,
            "ordinaryStayedNative": True,
            "registeredIds": ["ordinary", "pin"],
            "quadtreeUpdates": 1,
            "tickerCallbacks": 1,
            "previewStayedNative": True,
            "previewRegistered": False,
        },
        "unlocked": {
            "locked": False,
            "notesActive": True,
            "toolVisible": True,
            "updateType": "Note",
            "updates": [{"_id": "pin", "locked": False}],
            "calls": {
                "click": 1,
                "activate": 0,
                "hoverIn": 1,
                "hoverOut": 1,
                "releases": 0,
                "sortToggles": 1,
                "scenesRendered": 1,
                "controlsRendered": 1,
                "updateType": "Note",
                "updates": [{"_id": "pin", "locked": False}],
            },
        },
        "relocked": {
            "locked": True,
            "controlled": False,
            "calls": {
                "click": 2,
                "activate": 1,
                "hoverIn": 1,
                "hoverOut": 1,
                "releases": 1,
                "sortToggles": 1,
                "scenesRendered": 1,
                "controlsRendered": 1,
                "updateType": "Note",
                "updates": [{"_id": "pin", "locked": True}],
            },
        },
        "playerHasTool": False,
        "teardown": {
            "pinRestored": True,
            "registeredIds": ["ordinary", "pin"],
            "tickerCallbacks": 0,
        },
    }