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
    if (pin) return true;
    return originalHoverIn.apply(this, args);
  };

  prototype._onHoverOut = function(...args) {
    const pin = getMapPin(this.document);
    if (pin) return true;
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
});