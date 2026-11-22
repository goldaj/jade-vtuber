/* Private Live2D Web renderer. Canonical palette is loaded from Jade's
 * Python-backed /assets/intent-visuals.json; no duplicate hardcoded mapping.
 * Only existing r20 facial expressions are triggered. New motion assets must
 * be validated before their controls are connected.
 */
"use strict";
(() => {
  const target = document.getElementById("avatar-container");
  const fallback = document.getElementById("avatar-fallback");
  const status = document.getElementById("avatar-state");
  const mood = document.getElementById("mood-line");
  let model = null;
  let pixi = null;
  let mouth = 0;
  let palette = null;
  let pendingIntent = "neutral";
  let activeChoice = null;
  let observer = null;
  let visibilityObserver = null;
  let onScreen = true; // Graceful fallback if IntersectionObserver is unavailable.
  let renderRunning = false;
  let resetTimer = null;
  let speaking = false;
  const counts = Object.create(null);

  function applyExpression(expression) {
    if (!model) return;
    try {
      if (expression === "Neutral") {
        // pixi-live2d-display expression API differs between SDK versions.
        // Only use a supported reset method; never pass a fictional exp3 ID.
        const manager = model.internalModel?.motionManager?.expressionManager;
        if (manager && typeof manager.resetExpression === "function") {
          manager.resetExpression();
        }
        return;
      }
      if (typeof model.expression === "function") {
        const operation = model.expression(expression);
        if (operation && typeof operation.catch === "function") operation.catch(() => {});
      }
    } catch (_) {
      // A missing expression/SDK is optional: chat and voice must keep working.
    }
  }

  function clearTimer() {
    if (resetTimer !== null) clearTimeout(resetTimer);
    resetTimer = null;
  }

  function returnToIdle() {
    clearTimer();
    pendingIntent = "neutral";
    activeChoice = null;
    mood.textContent = "Jade est attentive.";
    applyExpression("Neutral");
  }

  function syncRenderVisibility() {
    if (!pixi || !pixi.ticker) return;
    // A hidden tab, an unmounted component or one outside the viewport has
    // no useful GPU output. Audio / LLM / message transport remain independent.
    const mounted = target.isConnected !== false &&
      (typeof target.getClientRects !== "function" || target.getClientRects().length > 0);
    const visible = Boolean(model && mounted && onScreen && !document.hidden);
    if (renderRunning === visible) return;
    renderRunning = visible;
    if (visible) {
      // A single resume, not a second ticker or a new Idle motion.
      if (typeof model.autoUpdate === "boolean") model.autoUpdate = true;
      pixi.ticker.start();
    } else {
      pixi.ticker.stop();
      if (model && typeof model.autoUpdate === "boolean") model.autoUpdate = false;
    }
  }

  document.addEventListener("visibilitychange", syncRenderVisibility);
  if (typeof IntersectionObserver === "function") {
    visibilityObserver = new IntersectionObserver(([entry]) => {
      onScreen = Boolean(entry?.isIntersecting);
      syncRenderVisibility();
    }, {threshold: .01});
    visibilityObserver.observe(target);
  }

  const avatar = {
    get ready() { return Boolean(model); },
    setMouth(value) {
      mouth = Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : 0;
    },
    setSpeaking(value) {
      speaking = Boolean(value);
      if (!speaking && pendingIntent !== "neutral") returnToIdle();
    },
    resetIntent() { returnToIdle(); },
    setIntent(label) {
      pendingIntent = label;
      if (!palette?.enabled) return;
      const key = Object.hasOwn(palette.intents, label) ? label : "neutral";
      const reactions = palette.intents[key];
      if (!Array.isArray(reactions) || !reactions.length) return;
      const index = counts[key] || 0;
      counts[key] = index + 1;
      const choice = reactions[index % reactions.length];
      if (!choice || typeof choice.text !== "string") return;
      activeChoice = choice;
      mood.textContent = choice.text;
      applyExpression(choice.expression);
      clearTimer();
      // Text-only replies return to idle. Long audio waits for onended.
      resetTimer = setTimeout(() => { if (!speaking) returnToIdle(); }, 12000);
    },
  };
  window.JadeAvatar = avatar;

  function resize() {
    if (!pixi || !model) return;
    const width = Math.max(1, target.clientWidth);
    const height = Math.max(1, target.clientHeight);
    pixi.renderer.resize(width, height);
    const naturalWidth = Math.max(model.width / (model.scale.x || 1), 1);
    const naturalHeight = Math.max(model.height / (model.scale.y || 1), 1);
    const scale = Math.min((width * .95) / naturalWidth, (height * 1.32) / naturalHeight);
    // Close framing places the unfinished lower edges of r20 below the scene.
    model.scale.set(Math.max(.05, scale * 1.5));
    // Offset the close-up to keep the bedside cup visible.
    model.position.set(width * .58, height * .79);
  }

  async function load() {
    try {
      const response = await fetch("/assets/intent-visuals.json", {
        mode: "same-origin", credentials: "omit", cache: "no-store"
      });
      if (response.ok) {
        const data = await response.json();
        if (data.version === 1 && data.intents && typeof data.enabled === "boolean") {
          palette = data;
        }
      }
    } catch (_) {
      // Optional palette; a failed request must never break the conversation.
    }
    const PIXI = window.PIXI;
    if (!PIXI || !PIXI.live2d || !PIXI.live2d.Live2DModel ||
        !window.Live2DCubismCore) {
      status.textContent = "Le décor est prêt. Le moteur Live2D doit encore être installé sur le PC (voir documentation).";
      return;
    }
    try {
      pixi = new PIXI.Application({
        resizeTo: target, autoDensity: true,
        resolution: Math.min(window.devicePixelRatio || 1, 2),
        antialias: true, backgroundAlpha: 0, transparent: true
      });
      target.appendChild(pixi.view);
      // The SDK can load asynchronously while the tab is invisible.
      // Prevent any rendering until the model is ready and visible.
      pixi.ticker.stop();
      renderRunning = false;
      model = await PIXI.live2d.Live2DModel.from("/model/Jade.model3.json", {
        autoInteract: false
      });
      // Core 6 moved render orders off drawables; the legacy renderer still
      // reads them through the adapter. r20 draws only drawable meshes.
      const cubism = model.internalModel.coreModel;
      if (!cubism.getDrawableRenderOrders()) {
        const core = cubism.getModel();
        if (core.getRenderOrders?.()?.length !== cubism.getDrawableCount()) {
          throw new Error("Cubism render order is incompatible with this model");
        }
        cubism.getDrawableRenderOrders = () => core.getRenderOrders();
      }
      model.anchor.set(.5, .5);
      pixi.stage.addChild(model);
      resize();
      observer = new ResizeObserver(resize);
      observer.observe(target);
      fallback.classList.add("hidden");
      pixi.ticker.add(() => {
        try {
          const core = model?.internalModel?.coreModel;
          if (core && typeof core.setParameterValueById === "function") {
            core.setParameterValueById("ParamMouthOpenY", mouth);
          }
        } catch (_) {}
      }, undefined, PIXI.UPDATE_PRIORITY?.LOW ?? -50);
      if (typeof model.motion === "function") {
        try {
          const animation = model.motion("Idle", 0);
          if (animation && animation.catch) animation.catch(() => {});
        } catch (_) {}
      }
      // Reapply the SAME chosen reaction after slow SDK loading, not the
      // next variant. One reply must never count as two emotional turns.
      if (activeChoice && palette?.enabled) applyExpression(activeChoice.expression);
      syncRenderVisibility();
    } catch (error) {
      console.warn("Jade Live2D:", error);
      if (observer) observer.disconnect();
      if (visibilityObserver) visibilityObserver.disconnect();
      if (pixi) { try { pixi.destroy(true, {children: true}); } catch (_) {} }
      pixi = null;
      model = null;
      status.textContent = "Impossible de charger le modèle r20 : vérifier Git LFS, WebGL et les composants Cubism.";
      fallback.classList.remove("hidden");
    }
  }
  load();
})();