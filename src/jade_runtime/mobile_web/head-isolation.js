/* Draw the r20 model in two depth passes without duplicating animation.
 * The actual Cubism drawable opacity buffer is masked AFTER model.update(),
 * so body/front hair and back hair can straddle the static seated sprite.
 * The original part isolation remains as a compatibility guard. */
"use strict";
(() => {
  const HIDE = Object.freeze([
    "PartJAD_BODY", "PartJAD_BODY_SKIN",
    "PartJAD_ARM_L", "PartJAD_ARM_R",
    "PartJAD_DRESS", "PartJAD_DRESS_SLEEVE_L",
    "PartJAD_DRESS_SLEEVE_R", "PartJAD_DRESS_SKIRT"
  ]);
  const REAR = new Set([
    "PartJAD_HAIR_BACK", "PartJAD_HAIR_BACK_L",
    "PartJAD_HAIR_BACK_C", "PartJAD_HAIR_BACK_R"
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

    // Cubism Core exposes each ArtMesh's parent part and its drawable opacity.
    // Altering that buffer while drawing is the only reliable way to separate
    // rear and front hair: toggling parent opacities without model.update()
    // would leave the already-evaluated drawable opacities unchanged.
    const parts = raw.parts;
    const drawables = raw.drawables;
    // Actual Cubism Web Core property: parts.parentIndices.
    const partParents = parts?.parentIndices ?? parts?.parentPartIndices;
    const drawableParents = drawables?.parentPartIndices;
    const alpha = drawables?.opacities;
    const drawableCount = drawables?.count;
    let rear = null;
    let body = null;
    if (partParents && drawableParents && alpha &&
        typeof alpha.set === "function" &&
        Number.isInteger(drawableCount) && drawableCount > 0 &&
        partParents.length >= count && drawableParents.length >= drawableCount &&
        alpha.length >= drawableCount) {
      const isPart = (start, wanted) => {
        let part = start;
        for (let depth = 0; depth < count && part >= 0 && part < count; depth++) {
          if (wanted(names[part])) return true;
          part = partParents[part];
        }
        return false;
      };
      const rearBits = new Uint8Array(drawableCount);
      const bodyBits = new Uint8Array(drawableCount);
      let rearCount = 0;
      let foregroundCount = 0;
      let bodyCount = 0;
      for (let i = 0; i < drawableCount; i++) {
        const parent = drawableParents[i];
        if (!Number.isInteger(parent) || parent < 0 || parent >= count) continue;
        if (isPart(parent, id => REAR.has(id))) {
          rearBits[i] = 1;
          rearCount++;
        } else {
          foregroundCount++;
        }
        if (isPart(parent, id => HIDE.includes(id))) {
          bodyBits[i] = 1;
          bodyCount++;
        }
      }
      // Never enter a hybrid scene unless both depth passes contain meshes.
      if (rearCount > 0 && foregroundCount > 0 && bodyCount > 0) {
        rear = rearBits;
        body = bodyBits;
      }
    }

    let wasSeated = false;
    return {
      sync(seated) {
        if (!seated && !wasSeated) return;
        indices.forEach((i, n) =>
          core.setPartOpacityByIndex(i, seated ? 0 : original[n]));
        wasSeated = seated;
      },
      // This executes inside internalModel.draw, after Cubism has evaluated
      // physics and mesh opacities. Values are restored even on WebGL failure.
      drawPass(pass, draw) {
        if (!rear || (pass !== "rear" && pass !== "front")) {
          throw new Error("Seated hair depth pass is unavailable");
        }
        const snapshot = alpha.slice(0, drawableCount);
        try {
          for (let i = 0; i < drawableCount; i++) {
            if (pass === "rear" ? !rear[i] : rear[i] || body[i]) alpha[i] = 0;
          }
          return draw();
        } finally {
          alpha.set(snapshot, 0);
        }
      },
      get canLayerHair() { return Boolean(rear); },
      get indices() { return indices.slice(); }
    };
  }
  window.JadeHeadIsolation = Object.freeze({forModel, hiddenPartIds:HIDE});
})();
