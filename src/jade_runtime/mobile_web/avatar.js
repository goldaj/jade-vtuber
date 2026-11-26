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
  let headIsolation = null;
  let seatedComposition = null;
  let pixi = null;
  let mouth = 0;
  let palette = null;
  let pendingIntent = "neutral";
  let activeChoice = null;
  let observer = null;
  let visibilityObserver = null;
  let onScreen = true; // Graceful fallback if IntersectionObserver is unavailable.
  let renderRunning = false;
  let hasStartedRendering = false;
  let resumeFromPause = false;
  let visibilityPauseTimer = null;
  const VIEWPORT_PAUSE_DELAY_MS = 6500;
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


  function isMounted() {
    return target.isConnected !== false &&
      (typeof target.getClientRects !== "function" || target.getClientRects().length > 0);
  }

  function cancelPendingVisibilityPause() {
    if (visibilityPauseTimer !== null) {
      clearTimeout(visibilityPauseTimer);
      visibilityPauseTimer = null;
    }
  }

  function stopRendering() {
    cancelPendingVisibilityPause();
    if (!pixi || !pixi.ticker) return;
    if (renderRunning) {
      renderRunning = false;
      pixi.ticker.stop();
      resumeFromPause = hasStartedRendering;
    }
    if (model && typeof model.autoUpdate === "boolean") model.autoUpdate = false;
  }

  function syncRenderVisibility() {
    if (!pixi || !pixi.ticker) return;
    // Hard stops must be immediate. Backgrounded tabs can throttle timers;
    // detached/hidden surfaces should never spend GPU time during the grace period.
    const hardHidden = document.hidden || !isMounted();
    const visible = Boolean(model && !hardHidden && onScreen);
    if (visible) {
      cancelPendingVisibilityPause();
      if (renderRunning) return;
      // After a real pause, restart only the visual expression from neutral.
      // Keep current speech, lips, dialogue and memory state untouched.
      if (resumeFromPause) {
        clearTimer();
        pendingIntent = "neutral";
        activeChoice = null;
        mood.textContent = "Jade est attentive.";
        applyExpression("Neutral");
        resumeFromPause = false;
      }
      if (typeof model.autoUpdate === "boolean") model.autoUpdate = true;
      renderRunning = true;
      hasStartedRendering = true;
      pixi.ticker.start();
      return;
    }
    if (hardHidden || !renderRunning || !model) {
      stopRendering();
      return;
    }
    // Soft viewport occlusion: a single grace timer avoids stop/start storms
    // on touch scrolls and temporary layout shifts. It is NOT a second ticker.
    if (visibilityPauseTimer !== null) return;
    visibilityPauseTimer = setTimeout(() => {
      visibilityPauseTimer = null;
      if (renderRunning && (document.hidden || !isMounted() || !onScreen)) {
        stopRendering();
      }
    }, VIEWPORT_PAUSE_DELAY_MS);
  }

  document.addEventListener("visibilitychange", syncRenderVisibility);
  document.querySelector?.(".room")?.addEventListener?.("jade-room-changed", () => resize());
  if (typeof IntersectionObserver === "function") {
    visibilityObserver = new IntersectionObserver(([entry]) => {
      onScreen = Boolean(entry?.isIntersecting);
      syncRenderVisibility();
    }, {threshold: .01});
    visibilityObserver.observe(target);
  }

  const avatar = {
    resize: () => resize(),
    get ready() { return Boolean(model); },
    get canIsolateHead() { return Boolean(headIsolation); },
    get canComposeSeated() {
      return Boolean(model && pixi && headIsolation?.canLayerHair &&
        window.PIXI?.Sprite?.from && window.PIXI?.Container);
    },
    prepareSeatedComposition(image) {
      if (seatedComposition) return true;
      if (!this.canComposeSeated || !image?.naturalWidth || !image?.naturalHeight) return false;
      const PIXI = window.PIXI;
      let back = null;
      let seatedBody = null;
      let previousRender = null;
      let previousDraw = null;
      try {
        // An already loaded HTML image can have a temporarily unuploaded Pixi
        // texture. Let Pixi upload it on the next frame rather than aborting.
        seatedBody = PIXI.Sprite.from(image);
        if (!seatedBody.texture) return false;
        back = new PIXI.Container();
        previousRender = model._render;
        previousDraw = model.internalModel.draw;
        const originalRender = previousRender.bind(model);
        const originalDraw = previousDraw.bind(model.internalModel);
        function gracefulFallback(error) {
          console.warn("Jade seated compositor disabled; static body retained:", error);
          const room = document.querySelector?.(".room");
          if (room) room.dataset.seatedCompositor = "false";
          if (seatedComposition) {
            seatedComposition.back.visible = false;
            seatedComposition.body.visible = false;
          }
        }
        let pass = null;
        // A single Cubism model is animated once; only its output is rendered
        // twice. The opacity mask runs AFTER its normal physics/motion update.
        model.internalModel.draw = gl => pass
          ? headIsolation.drawPass(pass, () => originalDraw(gl))
          : originalDraw(gl);
        function renderPass(renderer, name) {
          pass = name;
          try { originalRender(renderer); }
          finally { pass = null; }
        }
        back._render = renderer => {
          if (!isSeatedLayered()) return;
          try {
            model.updateTransform();
            renderPass(renderer, "rear");
          } catch (error) { gracefulFallback(error); }
        };
        model._render = renderer => {
          if (!isSeatedLayered()) {
            originalRender(renderer);
            return;
          }
          try { renderPass(renderer, "front"); }
          catch (error) {
            gracefulFallback(error);
            originalRender(renderer);
          }
        };
        back.visible = false;
        seatedBody.visible = false;
        pixi.stage.addChildAt(back, 0);
        pixi.stage.addChildAt(seatedBody, 1);
        seatedComposition = {back, body: seatedBody};
        return true;
      } catch (error) {
        if (previousRender) model._render = previousRender;
        if (previousDraw) model.internalModel.draw = previousDraw;
        if (back?.parent) back.parent.removeChild(back);
        if (seatedBody?.parent) seatedBody.parent.removeChild(seatedBody);
        if (seatedBody) seatedBody.destroy();
        console.warn("Seated Jade compositor:", error);
        return false;
      }
    },
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

  function isSeated() {
    const room = document.querySelector?.(".room");
    return room?.dataset.room === "bedroom" &&
      room?.dataset.seatedReady === "true";
  }

  function isSeatedLayered() {
    const room = document.querySelector?.(".room");
    return isSeated() && room?.dataset.seatedCompositor === "true";
  }

  function resize() {
    if (!pixi || !model) return;
    const width = Math.max(1, target.clientWidth);
    const height = Math.max(1, target.clientHeight);
    pixi.renderer.resize(width, height);
    const naturalWidth = Math.max(model.width / (model.scale.x || 1), 1);
    const naturalHeight = Math.max(model.height / (model.scale.y || 1), 1);
    const scale = Math.min((width * .95) / naturalWidth, (height * 1.32) / naturalHeight);
    const shell = document.querySelector?.(".shell");
    const room = document.querySelector?.(".room");
    const seated = isSeated();
    headIsolation?.sync(seated);
    if (seatedComposition) {
      seatedComposition.back.visible = seated && isSeatedLayered();
      seatedComposition.body.visible = seated && isSeatedLayered();
    }
    if (seated) {
      // Align the seated sprite inside the exact same 941x1672 scene plane.
      // These values come from the image crop, not device-specific pixels.
      const sprite = seatedComposition?.body;
      if (sprite) {
        const layout = window.JadeSeatedScene?.layout ?? {top: .406699, height: .562201};
        sprite.position.set(width * .127524, height * layout.top);
        sprite.width = width * .712009;
        sprite.height = height * layout.height;
      }
      const headScale = 1.30;
      model.scale.set(Math.max(.05, scale * headScale));
      // Keep the face above the illustrated neckline: the AVIF already
      // carries a full neck. Raise only the animated head and hair,
      // leaving the seated body and the kitchen camera unchanged.
      model.position.set(width * .555, height * .584);
      return;
    }
    const immersive = shell?.classList.contains("is-room-only");
    const miniScene = shell?.dataset?.view && shell.dataset.view !== "home" && !immersive;
    if (miniScene) {
      // Short menu scenes give the head the top edge. Scale the whole model,
      // keeping its proportions while allowing the lower body to be cropped.
      const miniScale = Math.min((width * .95) / naturalWidth, (height * 1.6) / naturalHeight);
      model.scale.set(Math.max(.05, miniScale));
      model.position.set(width * .5, Math.max(8, height * .04) + model.height * .5);
      return;
    }
    // Home and immersive kitchen keep their existing framing.
    model.scale.set(Math.max(.05, scale * (immersive ? 1.9 : 1.5)));
    model.position.set(width * (immersive ? .55 : .58), height * (immersive ? .82 : .79));
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
      headIsolation = window.JadeHeadIsolation?.forModel?.(cubism) ?? null;
      model.anchor.set(.5, .5);
      pixi.stage.addChild(model);
      resize();
      observer = new ResizeObserver(resize);
      observer.observe(target);
      fallback.classList.add("hidden");
      // Hybrid body activation needs a real head renderer, never a fallback.
      if (typeof Event === "function")
        document.querySelector?.(".room")?.dispatchEvent?.(new Event("jade-avatar-ready"));
      pixi.ticker.add(() => {
        try {
          const activeRoom = document.querySelector?.(".room");
          headIsolation?.sync(activeRoom?.dataset.room === "bedroom" &&
            activeRoom?.dataset.seatedReady === "true" && Boolean(seatedComposition));
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
      cancelPendingVisibilityPause();
      if (observer) observer.disconnect();
      if (visibilityObserver) visibilityObserver.disconnect();
      if (pixi) { try { pixi.destroy(true, {children: true}); } catch (_) {} }
      pixi = null;
      model = null;
      headIsolation = null;
      seatedComposition = null;
      status.textContent = "Impossible de charger le modèle r20 : vérifier Git LFS, WebGL et les composants Cubism.";
      fallback.classList.remove("hidden");
    }
  }
  load();
})();
