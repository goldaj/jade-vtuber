/* Private Live2D Web renderer. The server's visual palette supplies the
 * expression and caption. For r21, the same A/B choice also selects a motion.
 */
"use strict";
(() => {
  const target = document.getElementById("avatar-container");
  const fallback = document.getElementById("avatar-fallback");
  const status = document.getElementById("avatar-state");
  const mood = document.getElementById("mood-line");
  const room = document.querySelector?.(".room");
  const DEFAULT_PROFILE = Object.freeze({id:"classic", label:"Jade classique (r20)", available:true,
    manifestUrl:"/model/Jade.model3.json", presentation:"seated", classicIntents:true, idleMotion:"Idle"});
  let model = null;
  let modelLease = null;
  let activeProfile = null;
  let desiredProfile = null;
  let selectionVersion = 0;
  let selectionQueue = Promise.resolve();
  let pendingSelection = null;
  let cleanupBlocked = false;
  let standingCamera = null;
  let framing = {x:0, y:0, zoom:1};
  let shakeImpulse = null;
  let rendererState = Object.freeze({status:"idle", modelId:null, requestedId:"classic", message:""});
  let headIsolation = null;
  let seatedComposition = null;
  let pixi = null;
  let mouth = 0;
  let palette = null;
  let pendingIntent = "neutral";
  let activeChoice = null;
  let reactionVersion = 0;
  let releaseMotionBindings = null;
  let observer = null;
  let visibilityObserver = null;
  let onScreen = true; // Graceful fallback if IntersectionObserver is unavailable.
  let renderRunning = false;
  let hasStartedRendering = false;
  let resumeFromPause = false;
  let visibilityPauseTimer = null;
  const VIEWPORT_PAUSE_DELAY_MS = 6500;
  let resetTimer = null;
  let blinkTimer = null;
  let speaking = false;
  const counts = Object.create(null);
  const nextCounts = Object.create(null);
  const R21_MOTIONS = Object.freeze({
    neutral:"Neutral", playful:"Playful", excited:"Excited", curious:"Curious",
    tender:"Tender", reassuring:"Reassuring", serious:"Serious",
  });
  const R21_MOTION_PARAMETERS = [
    "ParamAngleX", "ParamAngleY", "ParamAngleZ", "ParamBodyAngleX", "ParamBodyAngleZ",
    "ParamBreath", "ParamBrowLY", "ParamJadeEarTwitchL", "ParamJadeEarTwitchR",
    "ParamJadeIdleLean", "ParamJadeLegRelaxL", "ParamJadeLegRelaxR", "ParamJadeWeightShift",
  ];
  const SHORT_EXPRESSIONS = new Set(["Blink", "WinkL", "WinkR"]);

  function playMotion(group, index, priority) {
    try { model?.motion?.(group, index, priority)?.catch?.(() => {}); }
    catch (_) { /* The avatar remains usable if an optional motion fails. */ }
  }

  function canShake() {
    return activeProfile?.id === "next" && rendererState.status === "ready" &&
      renderRunning && onScreen && !document.hidden && permitsFraming();
  }

  function stopShake() { shakeImpulse = null; }

  function nudgeFromShake(x, y) {
    if (!canShake() || !Number.isFinite(x) || !Number.isFinite(y)) return false;
    shakeImpulse = {x:clamp(x, -1, 1), y:clamp(y, -1, 1), started:performance.now()};
    return true;
  }

  function applyShake(core, now) {
    if (!shakeImpulse) return;
    const age = (now - shakeImpulse.started) / 1000;
    if (age >= .72 || !canShake()) {
      stopShake();
      return;
    }
    // The renderer keeps its own centre. The rig's angles feed the existing hair and clothes physics.
    const spring = Math.exp(-7 * age) * Math.sin(23 * age);
    const x = shakeImpulse.x * spring;
    const y = shakeImpulse.y * spring;
    core.addParameterValueById?.("ParamAngleX", 8 * x);
    core.addParameterValueById?.("ParamAngleY", 7 * y);
    core.addParameterValueById?.("ParamAngleZ", -6 * x);
    core.addParameterValueById?.("ParamBodyAngleX", 4 * x);
    core.addParameterValueById?.("ParamBodyAngleZ", -3 * x);
  }

  function bindR21MotionPlayback(internal, idleGroup) {
    const manager = internal.motionManager;
    const core = internal.coreModel;
    const defaultParameters = typeof core.getParameterDefaultValue === "function"
      ? R21_MOTION_PARAMETERS.map(id => core.getParameterIndex(id))
        .filter(index => index >= 0 && index < core.getParameterCount())
        .map(index => [index, core.getParameterDefaultValue(index)])
      : [];
    const resetMotionParameters = () => {
      // The SDK saves the last motion's pose. Start each frame at the rig's
      // neutral values so an interrupted gesture can fade out even if the
      // incoming motion has no curve for one of its parameters.
      for (const [index, value] of defaultParameters) core.setParameterValueByIndex(index, value);
    };
    const onMotionLoaded = (group, index, motion) => {
      if (group === idleGroup && index === 0) {
        // Pixi's 0.4 adapter builds the clip but ignores Meta.Loop.
        motion.setIsLoop?.(true);
        motion.setIsLoopFadeIn?.(false);
      }
    };

    // The adapter only ticks its automatic blink on frames without a motion.
    // r21 leaves the eye curves free, so do it ourselves before expressions
    // (which can then reliably close either eye).
    const blink = internal.eyeBlink;
    let lastBlinkUpdate = null;
    const updateBlink = () => {
      const now = performance.now();
      const delta = lastBlinkUpdate === null ? 0 : Math.min(.1, (now - lastBlinkUpdate) / 1000);
      lastBlinkUpdate = now;
      blink?.updateParameters(core, delta);
      applyShake(core, now);
    };
    const updateMouth = () => core.setParameterValueById("ParamMouthOpenY", mouth);
    internal.eyeBlink = undefined;
    internal.on?.("beforeMotionUpdate", resetMotionParameters);
    internal.on?.("afterMotionUpdate", updateBlink);
    internal.on?.("beforeModelUpdate", updateMouth);
    manager?.on?.("motionLoaded", onMotionLoaded);
    return () => {
      internal.off?.("beforeMotionUpdate", resetMotionParameters);
      internal.off?.("afterMotionUpdate", updateBlink);
      internal.off?.("beforeModelUpdate", updateMouth);
      manager?.off?.("motionLoaded", onMotionLoaded);
    };
  }

  function applyExpression(expression) {
    const r21 = activeProfile?.id === "next";
    if (!model || (!r21 && !activeProfile?.classicIntents)) return;
    try {
      if (expression === "Neutral") {
        const manager = model.internalModel?.motionManager?.expressionManager;
        if (r21 && manager?.defaultExpression) {
          // Cancel a pending expression download and permit the same wink on
          // another response. resetExpression alone only updates the queue.
          manager.reserveExpressionIndex = -1;
          manager.currentExpression = manager.defaultExpression;
        }
        manager?.resetExpression?.();
        return;
      }
      if (typeof model.expression === "function") {
        const operation = model.expression(expression);
        return operation?.catch?.(() => false) ?? operation;
      }
    } catch (_) {
      // A missing expression/SDK is optional: chat and voice must keep working.
    }
  }

  function clearTimer() {
    reactionVersion++;
    if (resetTimer !== null) clearTimeout(resetTimer);
    if (blinkTimer !== null) clearTimeout(blinkTimer);
    resetTimer = blinkTimer = null;
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
    stopShake();
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
        returnToIdle();
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
    selectModel,
    getTouchFrame, isModelAt, moveView, zoomView, resetView,
    nudgeFromShake, stopShake,
    get state() { return rendererState; },
    get ready() { return Boolean(model); },
    get usesSeatedBody() { return Boolean(model && activeProfile?.presentation === "seated"); },
    get canIsolateHead() { return Boolean(headIsolation); },
    get canComposeSeated() {
      return Boolean(this.usesSeatedBody && pixi && headIsolation?.canLayerHair &&
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
        if (!seatedBody.texture) throw new Error("Seated body texture unavailable");
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
        const composedModel = model;
        seatedComposition = {back, body: seatedBody, restore() {
          composedModel._render = previousRender;
          composedModel.internalModel.draw = previousDraw;
        }};
        return true;
      } catch (error) {
        let cleanupFailed = false;
        const clean = action => { try { action(); } catch (_) { cleanupFailed = true; } };
        clean(() => { if (previousRender) model._render = previousRender; });
        clean(() => { if (previousDraw) model.internalModel.draw = previousDraw; });
        clean(() => back?.parent?.removeChild(back));
        clean(() => seatedBody?.parent?.removeChild(seatedBody));
        clean(() => back?.destroy?.({children:true}));
        clean(() => seatedBody?.destroy?.({texture:true, baseTexture:true}));
        if (cleanupFailed) blockAfterCleanupFailure();
        console.warn("Seated Jade compositor:", error);
        return false;
      }
    },
    setMouth(value) {
      mouth = Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : 0;
    },
    setSpeaking(value) {
      const wasSpeaking = speaking;
      speaking = Boolean(value);
      if (activeProfile?.id === "next") {
        if (wasSpeaking && !speaking && activeChoice) returnToIdle();
      } else if (!speaking && pendingIntent !== "neutral") returnToIdle();
    },
    resetIntent() { returnToIdle(); },
    setIntent(label) {
      pendingIntent = label;
      if (!palette?.enabled) return;
      const key = Object.hasOwn(palette.intents, label) ? label : "neutral";
      const reactions = palette.intents[key];
      if (!Array.isArray(reactions) || !reactions.length) return;
      const r21 = activeProfile?.id === "next";
      const variants = r21 ? nextCounts : counts;
      const index = variants[key] || 0;
      variants[key] = index + 1;
      const choice = reactions[index % reactions.length];
      if (!choice || typeof choice.text !== "string") return;
      clearTimer();
      if (r21 && activeChoice?.expression !== choice.expression && SHORT_EXPRESSIONS.has(activeChoice?.expression)) {
        applyExpression("Neutral");
      }
      activeChoice = choice;
      mood.textContent = choice.text;
      const expression = applyExpression(choice.expression);
      if (r21) {
        // The adapter returns to its Idle group as soon as the gesture ends.
        const group = R21_MOTIONS[key];
        if (group) playMotion(group, index % 2, window.PIXI?.live2d?.MotionPriority?.FORCE ?? 3);
        if (SHORT_EXPRESSIONS.has(choice.expression)) {
          // The first blink may need to fetch its exp3 file. Count the brief
          // hold from the actual start rather than from the initial request.
          const version = reactionVersion;
          void Promise.resolve(expression).then(() => {
            if (version !== reactionVersion) return;
            blinkTimer = setTimeout(() => {
              blinkTimer = null;
              applyExpression("Neutral");
            }, 260);
          });
        }
      }
      // Text-only replies clear their expression/caption. For longer audio,
      // the last source ending invokes setSpeaking(false).
      resetTimer = setTimeout(() => { if (!speaking) returnToIdle(); }, 12000);
    },
  };
  window.JadeAvatar = avatar;

  function isSeated() {
    const room = document.querySelector?.(".room");
    return activeProfile?.presentation === "seated" && room?.dataset.room === "bedroom" &&
      room?.dataset.seatedReady === "true";
  }

  function isSeatedLayered() {
    const room = document.querySelector?.(".room");
    return isSeated() && room?.dataset.seatedCompositor === "true";
  }

  // Neutral eye centres and eye spacing measured in the two shipped moc3 exports.
  const CLASSIC_CAMERA = {width:3840, height:4160, eyeX:1745, eyeY:871, eyeSpacing:365};
  const R21_EYES = {y:761 / 5000, spacing:289 / 3840};
  // Solid areas of the published r21 canvas, in fractions of its width and height.
  const R21_GRAB_AREAS = [
    [.50, .15, .125, .12], [.50, .30, .110, .09], [.50, .48, .15, .11],
    [.447, .73, .039, .19], [.543, .73, .039, .19],
  ];
  const R21_GRAB_DRAWABLES = new Set([
    "JAD_R21_HAIR_AHOGE", "JAD_R21_RESTORED_HAIR_CAP", "JAD_R21_RESTORED_HAIR_BACK",
    "JAD_R21_RESTORED_HAIR_LOCK_R", "JAD_R21_RESTORED_HAIR_LOCK_L",
    "JAD_R21_RESTORED_EAR_R", "JAD_R21_RESTORED_EAR_L", "JAD_R21_RESTORED_FACE",
    "JAD_R21_RESTORED_NECK", "JAD_R21_RESTORED_TORSO", "JAD_R21_ARM_L_WHOLE", "JAD_R21_ARM_R_WHOLE",
    "JAD_R21_RESTORED_SKIRT", "JAD_R21_LEG_FOOT_L_CONTINUOUS", "JAD_R21_LEG_FOOT_R_CONTINUOUS",
  ]);
  const clamp = (value, minimum, maximum) => Math.max(minimum, Math.min(maximum, value));

  function permitsFraming() {
    const shell = document.querySelector?.(".shell");
    return shell?.dataset.view === "home" || shell?.classList.contains("is-room-only");
  }

  function framingLayout() {
    const canvas = target.getBoundingClientRect?.();
    const scene = room?.getBoundingClientRect?.();
    if (!canvas?.width || !canvas.height || !scene?.width || !scene.height ||
        !target.clientWidth || !target.clientHeight) return null;
    const cssX = canvas.width / target.clientWidth;
    const cssY = canvas.height / target.clientHeight;
    const left = (Math.max(0, scene.left, canvas.left) - canvas.left) / cssX;
    const top = (Math.max(0, scene.top, canvas.top) - canvas.top) / cssY;
    const right = (Math.min(window.innerWidth || Infinity, scene.right, canvas.right) - canvas.left) / cssX;
    const bottom = (Math.min(window.innerHeight || Infinity, scene.bottom, canvas.bottom) - canvas.top) / cssY;
    if (right <= left || bottom <= top) return null;
    return {canvas, cssX, cssY, left, top, right, bottom, width: right - left, height: bottom - top};
  }

  function activeFramingLayout() {
    if (!standingCamera || rendererState.status !== "ready" || activeProfile?.id !== "next" ||
        !permitsFraming() || document.hidden) return null;
    return framingLayout();
  }

  function notifyFraming() {
    if (typeof Event === "function") room?.dispatchEvent?.(new Event("jade-avatar-framing"));
  }

  function applyFraming(layout, commit = false) {
    const base = standingCamera;
    let {x, y, scale} = base;
    if (layout && (framing.x || framing.y || framing.zoom !== 1)) {
      x += framing.x * layout.width;
      y += framing.y * layout.height;
      scale *= framing.zoom;

      // Keep the nearest solid part in reach. A bounding box alone would let the
      // empty corner around Jade's shoulders or feet be the only part left onscreen.
      const insetX = Math.min(30, layout.width / 2);
      const insetY = Math.min(30, layout.height / 2);
      let correctionX = 0, correctionY = 0, nearest = Infinity;
      for (const [anchorX, anchorY] of R21_GRAB_AREAS) {
        const px = x + (anchorX - .5) * base.width * scale;
        const py = y + (anchorY - .5) * base.height * scale;
        const dx = clamp(px, layout.left + insetX, layout.right - insetX) - px;
        const dy = clamp(py, layout.top + insetY, layout.bottom - insetY) - py;
        const distance = Math.hypot(dx, dy);
        if (distance < nearest) {
          nearest = distance;
          correctionX = dx;
          correctionY = dy;
        }
      }
      x += correctionX;
      y += correctionY;
      if (commit) {
        framing.x = (x - base.x) / layout.width;
        framing.y = (y - base.y) / layout.height;
      }
    }
    model.scale.set(scale);
    model.position.set(x, y);
    notifyFraming();
  }

  function getTouchFrame(layout = activeFramingLayout()) {
    if (!layout) return null;
    const {canvas, cssX, cssY} = layout;
    const {width, height} = standingCamera;
    const scale = model.scale.x;
    const x = model.position.x, y = model.position.y;
    // The interaction surface covers the painted character, including the hair's
    // movement margin. The actual contact is checked against visible triangles.
    const left = Math.max(layout.left, x - .22 * width * scale);
    const top = Math.max(layout.top, y - .50 * height * scale);
    const right = Math.min(layout.right, x + .22 * width * scale);
    const bottom = Math.min(layout.bottom, y + .46 * height * scale);
    if (right <= left || bottom <= top) return null;
    return {left: canvas.left + left * cssX, top: canvas.top + top * cssY,
      right: canvas.left + right * cssX, bottom: canvas.top + bottom * cssY};
  }

  function pointInMesh(x, y, vertices, indices) {
    for (let i = 0; i + 2 < indices.length; i += 3) {
      const a = indices[i] * 2, b = indices[i + 1] * 2, c = indices[i + 2] * 2;
      const ax = vertices[a], ay = vertices[a + 1];
      const abx = vertices[b] - ax, aby = vertices[b + 1] - ay;
      const acx = vertices[c] - ax, acy = vertices[c + 1] - ay;
      const area = abx * acy - aby * acx;
      if (!area) continue;
      const u = ((x - ax) * acy - (y - ay) * acx) / area;
      const v = (abx * (y - ay) - aby * (x - ax)) / area;
      if (u >= 0 && v >= 0 && u + v <= 1) return true;
    }
    return false;
  }

  function isModelAt(clientX, clientY) {
    const layout = activeFramingLayout();
    const frame = getTouchFrame(layout);
    if (!frame || !Number.isFinite(clientX) || !Number.isFinite(clientY) ||
        clientX < frame.left || clientX > frame.right || clientY < frame.top || clientY > frame.bottom) return false;
    const scale = model.scale.x;
    const x = ((clientX - layout.canvas.left) / layout.cssX - model.position.x) / (standingCamera.width * scale);
    const y = ((clientY - layout.canvas.top) / layout.cssY - model.position.y) / (standingCamera.height * scale);
    const cubism = model.internalModel?.coreModel?.getModel?.();
    const {canvasinfo, drawables} = cubism || {};
    if (canvasinfo?.PixelsPerUnit && drawables?.ids && drawables.indices && drawables.vertexPositions && drawables.opacities) {
      const meshX = x * canvasinfo.CanvasWidth / canvasinfo.PixelsPerUnit;
      const meshY = -y * canvasinfo.CanvasHeight / canvasinfo.PixelsPerUnit;
      let knownModel = false;
      for (let i = 0; i < drawables.ids.length; i++) {
        if (!R21_GRAB_DRAWABLES.has(drawables.ids[i])) continue;
        knownModel = true;
        const vertices = drawables.vertexPositions[i], indices = drawables.indices[i];
        if (drawables.opacities[i] > .08 && vertices?.length && indices?.length &&
            pointInMesh(meshX, meshY, vertices, indices))
          return true;
      }
      if (knownModel) return false;
    }
    // Portable r21 bundles may use other drawable names. Use the calibrated
    // solid areas for those bundles rather than accepting the blank canvas.
    return R21_GRAB_AREAS.some(([cx, cy, rx, ry]) => ((x + .5 - cx) / rx) ** 2 + ((y + .5 - cy) / ry) ** 2 <= 1);
  }

  function moveView(dx, dy) {
    const layout = activeFramingLayout();
    if (!layout || !Number.isFinite(dx) || !Number.isFinite(dy)) return false;
    framing.x = (model.position.x - standingCamera.x + dx / layout.cssX) / layout.width;
    framing.y = (model.position.y - standingCamera.y + dy / layout.cssY) / layout.height;
    applyFraming(layout, true);
    return true;
  }

  function zoomView(factor, clientX, clientY) {
    const layout = activeFramingLayout();
    if (!layout || !Number.isFinite(factor) || factor <= 0 ||
        !Number.isFinite(clientX) || !Number.isFinite(clientY)) return false;
    const zoom = clamp(framing.zoom * factor, .45, 2.5);
    const ratio = zoom / framing.zoom;
    if (ratio === 1) return true;
    const x = (clientX - layout.canvas.left) / layout.cssX;
    const y = (clientY - layout.canvas.top) / layout.cssY;
    framing.x = (x + (model.position.x - x) * ratio - standingCamera.x) / layout.width;
    framing.y = (y + (model.position.y - y) * ratio - standingCamera.y) / layout.height;
    framing.zoom = zoom;
    applyFraming(layout, true);
    return true;
  }

  function resetView() {
    if (!activeFramingLayout()) return false;
    framing = {x:0, y:0, zoom:1};
    applyFraming(null);
    return true;
  }

  function placeModel(scale, x, y, width, height) {
    if (activeProfile?.id === "next") {
      const nextScale = scale * CLASSIC_CAMERA.eyeSpacing / (width * R21_EYES.spacing);
      // Align the eyes on the old camera's plane while keeping the standing rig's proportions.
      x += scale * (CLASSIC_CAMERA.eyeX - CLASSIC_CAMERA.width / 2);
      y += scale * (CLASSIC_CAMERA.eyeY - CLASSIC_CAMERA.height / 2)
        - nextScale * height * (R21_EYES.y - .5);
      standingCamera = {x, y, scale:nextScale, width, height};
      applyFraming(permitsFraming() ? framingLayout() : null);
      return;
    }
    model.scale.set(scale);
    model.position.set(x, y);
  }

  function resize() {
    if (!pixi || !model) return;
    const width = Math.max(1, target.clientWidth);
    const height = Math.max(1, target.clientHeight);
    pixi.renderer.resize(width, height);
    const naturalWidth = Math.max(model.width / (model.scale.x || 1), 1);
    const naturalHeight = Math.max(model.height / (model.scale.y || 1), 1);
    const r21 = activeProfile?.id === "next";
    const standingBedroom = r21 && room?.dataset.room === "bedroom" && room.dataset.portraitReady === "true";
    // The lifted standing avatar can render beyond its camera frame down to the room edge.
    const cameraViewportHeight = standingBedroom ? target.parentElement?.clientHeight || height : height;
    const cameraWidth = r21 ? CLASSIC_CAMERA.width : naturalWidth;
    const cameraHeight = r21 ? CLASSIC_CAMERA.height : naturalHeight;
    const scale = Math.min((width * .95) / cameraWidth, (cameraViewportHeight * 1.32) / cameraHeight);
    const shell = document.querySelector?.(".shell");
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
    }
    if (seated || standingBedroom) {
      const headScale = 1.30;
      placeModel(Math.max(.05, scale * headScale), width * .555, cameraViewportHeight * .584,
        naturalWidth, naturalHeight);
      return;
    }
    const immersive = shell?.classList.contains("is-room-only");
    const miniScene = shell?.dataset?.view && shell.dataset.view !== "home" && !immersive;
    if (miniScene) {
      // Short menu scenes give the head the top edge. Scale the whole model,
      // keeping its proportions while allowing the lower body to be cropped.
      const miniScale = Math.max(.05, Math.min((width * .95) / cameraWidth, (height * 1.6) / cameraHeight));
      placeModel(miniScale, width * .5, Math.max(8, height * .04) + cameraHeight * miniScale * .5,
        naturalWidth, naturalHeight);
      return;
    }
    placeModel(Math.max(.05, scale * (immersive ? 1.9 : 1.5)),
      width * (immersive ? .55 : .58), height * (immersive ? .82 : .79),
      naturalWidth, naturalHeight);
  }

  function publishState(nextStatus, message = "") {
    rendererState = Object.freeze({status:nextStatus, modelId:activeProfile?.id || null,
      requestedId:desiredProfile?.id || "classic", message});
    if (typeof Event === "function") room?.dispatchEvent?.(new Event("jade-avatar-state"));
  }

  function profileFor(id) {
    return window.JadeModelCatalog ? window.JadeModelCatalog.get(id)
      : id === "classic" ? DEFAULT_PROFILE : null;
  }

  function setPresentation(profile) {
    if (room) room.dataset.avatarPresentation = profile.presentation;
  }

  function blockAfterCleanupFailure() {
    cleanupBlocked = true;
    status.textContent = "L’affichage doit être relancé. Recharge le salon pour réessayer.";
    fallback.classList.remove("hidden");
    publishState("error", status.textContent);
  }

  function releaseCurrentModel() {
    const errors = [];
    const attempt = fn => { try { fn(); } catch (error) { errors.push(error); } };
    attempt(returnToIdle);
    mouth = 0;
    speaking = false;
    attempt(() => releaseMotionBindings?.());
    releaseMotionBindings = null;
    // Hide the old DOM body before any asynchronous replacement begins.
    attempt(() => window.JadeSeatedScene?.deactivate?.());
    if (room) {
      room.dataset.seatedReady = "false";
      room.dataset.seatedCompositor = "false";
      delete room.dataset.avatarModel;
    }
    attempt(stopRendering);
    cancelPendingVisibilityPause();
    if (seatedComposition) {
      const composition = seatedComposition;
      seatedComposition = null;
      attempt(() => composition.restore?.());
      attempt(() => composition.back.parent?.removeChild(composition.back));
      attempt(() => composition.body.parent?.removeChild(composition.body));
      attempt(() => composition.back.destroy?.({children:true}));
      attempt(() => composition.body.destroy?.({texture:true, baseTexture:true}));
    }
    if (modelLease) attempt(() => modelLease.dispose());
    modelLease = null;
    model = null;
    activeProfile = null;
    standingCamera = null;
    framing = {x:0, y:0, zoom:1};
    headIsolation = null;
    renderRunning = false;
    hasStartedRendering = false;
    resumeFromPause = false;
    if (errors.length) {
      const error = new Error("Previous model could not be released");
      error.cleanupFailed = true;
      throw error;
    }
  }

  function ensureRenderer() {
    if (pixi) return;
    const PIXI = window.PIXI;
    if (!PIXI?.Application || !window.Live2DCubismCore || !window.JadeAvatarModelLoader)
      throw new Error("Live2D renderer unavailable");
    pixi = new PIXI.Application({resizeTo:target, autoDensity:true,
      resolution:Math.min(window.devicePixelRatio || 1, 2),
      antialias:true, backgroundAlpha:0, transparent:true});
    target.appendChild(pixi.view);
    pixi.ticker.stop();
    // One canvas, observer and ticker for the whole session, never one per choice.
    pixi.ticker.add(() => {
      try {
        // DOM fallback still needs to hide the model's original standing body.
        headIsolation?.sync(isSeated());
        const core = model?.internalModel?.coreModel;
        if (activeProfile?.id !== "next" && typeof core?.setParameterValueById === "function")
          core.setParameterValueById("ParamMouthOpenY", mouth);
      } catch (_) {}
    }, undefined, PIXI.UPDATE_PRIORITY?.LOW ?? -50);
    observer = new ResizeObserver(resize);
    observer.observe(target);
  }

  function mountModel(lease, profile) {
    const next = lease.model;
    const cubism = next.internalModel.coreModel;
    if (!cubism.getDrawableRenderOrders()) {
      const core = cubism.getModel();
      if (core.getRenderOrders?.()?.length !== cubism.getDrawableCount())
        throw new Error("Cubism render order is incompatible with this model");
      cubism.getDrawableRenderOrders = () => core.getRenderOrders();
    }
    modelLease = lease;
    model = next;
    activeProfile = profile;
    setPresentation(profile);
    if (room) room.dataset.avatarModel = profile.id;
    headIsolation = profile.presentation === "seated"
      ? window.JadeHeadIsolation?.forModel?.(cubism) ?? null : null;
    model.anchor.set(.5, .5);
    pixi.stage.addChild(model);
    resize();
    fallback.classList.add("hidden");
    if (typeof Event === "function") room?.dispatchEvent?.(new Event("jade-avatar-ready"));
    if (profile.id === "next") releaseMotionBindings = bindR21MotionPlayback(next.internalModel, profile.idleMotion);
    if (profile.idleMotion) playMotion(profile.idleMotion, 0,
      profile.id === "next" ? window.PIXI?.live2d?.MotionPriority?.IDLE ?? 1 : undefined);
    syncRenderVisibility();
  }

  async function switchTo(profile, version, recovering = false) {
    if (cleanupBlocked || version !== selectionVersion) return false;
    if (model && activeProfile?.id === profile.id) {
      publishState("ready");
      return true;
    }
    let lease = null;
    try {
      ensureRenderer();
      releaseCurrentModel();
      setPresentation(profile);
      fallback.classList.remove("hidden");
      status.textContent = "Chargement de Jade…";
      publishState("loading", recovering
        ? "Retour au modèle classique…" : "Chargement du modèle…");
      lease = await window.JadeAvatarModelLoader.load(profile);
      if (version !== selectionVersion) {
        lease.dispose();
        return false;
      }
      mountModel(lease, profile);
      publishState("ready", recovering
        ? "Jade r21 n’a pas pu être chargée. Le modèle classique est rétabli." : "");
      return true;
    } catch (error) {
      console.warn("Jade Live2D:", error);
      try {
        if (modelLease === lease && lease) releaseCurrentModel();
        else if (lease) lease.dispose();
      } catch (cleanupError) { error = cleanupError; }
      if (error?.cleanupFailed) {
        blockAfterCleanupFailure();
        return false;
      }
      if (version !== selectionVersion) return false;
      if (profile.id !== "classic" && !recovering) {
        await switchTo(profileFor("classic") || DEFAULT_PROFILE, version, true);
        return false;
      }
      status.textContent = "Impossible de charger Jade. Recharge le salon pour réessayer.";
      fallback.classList.remove("hidden");
      publishState("error", status.textContent);
      return false;
    }
  }

  function selectModel(id) {
    if (cleanupBlocked) return Promise.resolve(false);
    const profile = profileFor(id);
    if (!profile?.available || !profile.manifestUrl) {
      publishState(rendererState.status, "Ce modèle n’est pas encore disponible.");
      return Promise.resolve(false);
    }
    if (pendingSelection?.id === id) return pendingSelection.promise;
    desiredProfile = profile;
    const version = ++selectionVersion;
    // A later request never starts while an older SDK setup is unsettled.
    // Obsolete loads are disposed without mounting before this queue advances.
    const promise = selectionQueue.then(() => switchTo(profile, version)).finally(() => {
      if (pendingSelection?.version === version) pendingSelection = null;
    });
    selectionQueue = promise.catch(() => {});
    pendingSelection = {id, version, promise};
    return promise;
  }

  async function start() {
    try {
      const response = await fetch("/assets/intent-visuals.json", {
        mode:"same-origin", credentials:"omit", cache:"no-store"
      });
      if (response.ok) {
        const data = await response.json();
        if (data.version === 1 && data.intents && typeof data.enabled === "boolean") palette = data;
      }
    } catch (_) { /* Optional palette never prevents loading the default model. */ }
    await window.JadeModelCatalog?.ready;
    if (!desiredProfile) await selectModel(window.JadeModelCatalog?.defaultId || "classic");
  }
  void start();
})();
