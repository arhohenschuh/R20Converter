Hooks.once("init", () => {
  const NoteClass = CONFIG.Note?.objectClass;
  const prototype = NoteClass?.prototype;
  if (!prototype || prototype.__r20MapPinClickPatched) return;
  const getMapPin = document => document?.flags?.R20Converter?.mapPin ?? null;

  const originalClick = prototype._onClickLeft;
  const originalActivate = prototype._onClickLeft2;
  const originalCanControl = prototype._canControl;
  const originalCanView = prototype._canView;
  const originalHoverIn = prototype._onHoverIn;
  const originalHoverOut = prototype._onHoverOut;
  const originalUpdateQuadtree = prototype._updateQuadtree;
  const NotesLayerClass = CONFIG.Canvas?.layers?.notes?.layerClass;
  const notesLayerPrototype = NotesLayerClass?.prototype;
  let mapPinLayer = null;
  let mapPinTicker = null;
  let editMode = false;
  let visibilityOwner = prototype;
  let originalVisibility;
  while (visibilityOwner && !originalVisibility) {
    originalVisibility = Object.getOwnPropertyDescriptor(visibilityOwner, "isVisible");
    visibilityOwner = Object.getPrototypeOf(visibilityOwner);
  }
  if (typeof originalVisibility?.get !== "function") {
    throw new Error("R20Converter Map Pins require Note.isVisible");
  }

  Object.defineProperty(prototype, "isVisible", {
    configurable: originalVisibility.configurable,
    enumerable: originalVisibility.enumerable,
    get() {
      const pin = getMapPin(this.document);
      if (pin && pin.visibleTo !== "all" && !game.user.isGM) return false;
      return originalVisibility.get.call(this);
    },
  });

  const sceneMapPins = () => (globalThis.canvas?.scene?.notes || [])
    .map(document => document.object)
    .filter(note => note && getMapPin(note.document));

  const syncMapPinLayerVisibility = () => {
    if (mapPinLayer) mapPinLayer.visible = Boolean(globalThis.canvas?.notes?.objects?.visible);
  };

  const restoreMapPins = () => {
    if (!mapPinLayer) return;
    const layer = mapPinLayer;
    mapPinLayer = null;
    if (mapPinTicker) {
      mapPinTicker.remove(syncMapPinLayerVisibility);
      mapPinTicker = null;
    }
    const objects = globalThis.canvas?.notes?.objects;
    if (objects && !objects.destroyed) {
      for (const note of [...layer.children]) {
        if (!note.destroyed) objects.addChild(note);
      }
    }
    layer.parent?.removeChild(layer);
    layer.destroy({children: false});
  };

  const moveMapPinBelowTokens = note => {
    if (!mapPinLayer || note?.isPreview || !getMapPin(note?.document)
        || note.parent === mapPinLayer) return;
    mapPinLayer.addChild(note);
    note._updateQuadtree?.();
  };

  const mountMapPinLayer = () => {
    restoreMapPins();
    const board = globalThis.canvas;
    const pins = [...(board?.notes?.objects?.children || [])]
      .filter(note => getMapPin(note.document));
    if (!pins.length || !board?.interface || !globalThis.PIXI?.Container) return;
    mapPinLayer = new PIXI.Container();
    mapPinLayer.name = "R20ConverterMapPins";
    mapPinLayer.zIndex = (board.tokens?.zIndex ?? 200) - 1;
    mapPinLayer.sortableChildren = true;
    board.interface.addChild(mapPinLayer);
    board.interface.sortChildren();
    for (const pin of pins) moveMapPinBelowTokens(pin);
    editMode = pins.every(pin => !pin.document.locked);
    syncMapPinLayerVisibility();
    mapPinTicker = board.app?.ticker || null;
    mapPinTicker?.add(syncMapPinLayerVisibility);
    globalThis.ui?.controls?.render({force: true});
  };

  if (notesLayerPrototype) {
    let placeablesOwner = notesLayerPrototype;
    let originalPlaceables;
    while (placeablesOwner && !originalPlaceables) {
      originalPlaceables = Object.getOwnPropertyDescriptor(placeablesOwner, "placeables");
      placeablesOwner = Object.getPrototypeOf(placeablesOwner);
    }
    if (typeof originalPlaceables?.get === "function") {
      Object.defineProperty(notesLayerPrototype, "placeables", {
        configurable: originalPlaceables.configurable,
        enumerable: originalPlaceables.enumerable,
        get() {
          const native = originalPlaceables.get.call(this);
          if (this !== globalThis.canvas?.notes || !mapPinLayer || mapPinLayer.destroyed) return native;
          return [...native, ...mapPinLayer.children.filter(note => !note.destroyed && !note.isPreview)];
        },
      });
    }
  }

  if (typeof originalUpdateQuadtree === "function") {
    prototype._updateQuadtree = function() {
      const pin = getMapPin(this.document);
      if (pin && mapPinLayer && this.parent === mapPinLayer) {
        const layer = this.layer;
        if (!layer?.quadtree || this.isPreview) return;
        if (this.destroyed) layer.quadtree.remove(this);
        else layer.quadtree.update({r: this.bounds, t: this});
        return;
      }
      return originalUpdateQuadtree.call(this);
    };
  }

  const setEditMode = async active => {
    if (!game.user.isGM || !globalThis.canvas?.scene) return;
    const pins = sceneMapPins();
    editMode = Boolean(active);
    const locked = !editMode;
    const updates = pins.filter(pin => pin.document.locked !== locked)
      .map(pin => ({_id: pin.id, locked}));
    if (updates.length) await canvas.scene.updateEmbeddedDocuments("Note", updates);
    if (!editMode) {
      for (const pin of pins) {
        if (pin.controlled) pin.release();
      }
    }
    for (const pin of pins) pin.renderFlags.set({refreshState: true});
  };

  prototype._canControl = function(user, event) {
    const pin = getMapPin(this.document);
    if (pin) return this._canView(user, event);
    return originalCanControl.call(this, user, event);
  };

  prototype._canView = function(user, event) {
    user ||= game.user;
    const pin = getMapPin(this.document);
    if (pin && pin.visibleTo !== "all" && !user.isGM) return false;
    return originalCanView.call(this, user, event);
  };

  prototype._onHoverIn = function(...args) {
    const pin = getMapPin(this.document);
    if (pin && !(editMode && game.user.isGM)) return true;
    return originalHoverIn.apply(this, args);
  };

  prototype._onHoverOut = function(...args) {
    const pin = getMapPin(this.document);
    if (pin && !(editMode && game.user.isGM)) return true;
    return originalHoverOut.apply(this, args);
  };

  function activateMapPin(note, event, pin) {
    const activatedAt = Date.now();
    if (activatedAt - (note.__r20MapPinActivatedAt || 0) < 500) return true;
    note.__r20MapPinActivatedAt = activatedAt;
    let hookId;
    if (pin.subLink) {
      const targetNote = note;
      hookId = Hooks.on("activateNote", (activatedNote, options) => {
        if (activatedNote === targetNote) {
          const heading = String(pin.subLink).trim();
          const tocHeading = Object.values(targetNote.document.page?.toc || {})
            .find(candidate => String(candidate.text).trim() === heading);
          options.anchor = tocHeading?.slug
            || JournalEntryPage.implementation.slugifyHeading(heading);
        }
      });
    }
    try {
      return originalActivate.call(note, event);
    } finally {
      if (hookId !== undefined) Hooks.off("activateNote", hookId);
    }
  }

  prototype._onClickLeft = function(event) {
    const pin = getMapPin(this.document);
    if (!pin) return originalClick.call(this, event);
    if (editMode && game.user.isGM) return originalClick.call(this, event);
    if (originalCanControl.call(this, game.user, event)) originalClick.call(this, event);
    return activateMapPin(this, event, pin);
  };

  prototype._onClickLeft2 = function(event) {
    const pin = getMapPin(this.document);
    if (pin) return activateMapPin(this, event, pin);
    return originalActivate.call(this, event);
  };

  Object.defineProperty(prototype, "__r20MapPinClickPatched", {
    value: true,
    configurable: false,
    enumerable: false,
  });

  if (notesLayerPrototype && globalThis.PIXI?.Container) {
    Hooks.on("canvasReady", mountMapPinLayer);
    Hooks.on("canvasTearDown", restoreMapPins);
    Hooks.on("drawNote", moveMapPinBelowTokens);
    Hooks.on("getSceneControlButtons", controls => {
      if (!game.user.isGM || !controls.notes) return;
      controls.notes.tools.r20MapPinEdit = {
        name: "r20MapPinEdit",
        order: 4.5,
        title: "Unlock and Move Map Pins",
        icon: "fa-solid fa-arrows-up-down-left-right",
        visible: sceneMapPins().length > 0,
        toggle: true,
        active: editMode,
        onChange: async (_event, active) => {
          canvas.notes.activate();
          await setEditMode(active);
        },
      };
    });
  }

  Hooks.once("ready", () => {
    if (game.scenes?.sortingMode === "m") return;
    game.scenes?.toggleSortingMode();
    globalThis.ui?.scenes?.render({force: true});
  });
});