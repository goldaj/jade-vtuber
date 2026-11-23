/* Hide r20 standing body parts at their Cubism source. Never clip animated hair. */
"use strict";
(() => {
  const HIDE = Object.freeze([
    "PartJAD_BODY", "PartJAD_BODY_SKIN",
    "PartJAD_ARM_L", "PartJAD_ARM_R",
    "PartJAD_DRESS", "PartJAD_DRESS_SLEEVE_L",
    "PartJAD_DRESS_SLEEVE_R", "PartJAD_DRESS_SKIRT"
  ]);
  function label(value) {
    if (typeof value === "string") return value;
    if (typeof value?.getString === "function") return value.getString();
    return String(value ?? "");
  }
  function forModel(core) {
    const raw = core?.getModel?.();
    const ids = raw?.parts?.ids || raw?.getPartIds?.();
    const count = core?.getPartCount?.() ?? raw?.parts?.count;
    if (!ids || !Number.isInteger(count) || count < HIDE.length ||
        typeof core?.setPartOpacityByIndex !== "function") return null;
    const names = Array.from(ids, label);
    const indices = HIDE.map(id => {
      const index = names.indexOf(id);
      if (index >= 0) return index;
      return typeof core.getPartIndex === "function" ? core.getPartIndex(id) : -1;
    });
    if (indices.some(i => !Number.isInteger(i) || i < 0 || i >= count)) return null;
    const original = indices.map(i => {
      const opacity = core.getPartOpacityByIndex?.(i);
      return Number.isFinite(opacity) ? opacity : 1;
    });
    let wasSeated = false;
    return {
      sync(seated) {
        if (!seated && !wasSeated) return;
        indices.forEach((i,n) =>
          core.setPartOpacityByIndex(i, seated ? 0 : original[n]));
        wasSeated = seated;
      },
      get indices() { return indices.slice(); }
    };
  }
  window.JadeHeadIsolation = Object.freeze({forModel, hiddenPartIds:HIDE});
})();