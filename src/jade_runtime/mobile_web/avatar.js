/* Private Live2D Web renderer. The server's palette supplies the caption and
 * classic expressions. r21 holds a face pose around a single A/B motion.
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
  let shakeLayer = null;
  let rendererState = Object.freeze({status:"idle", modelId:null, requestedId:"classic", message:""});
  let headIsolation = null;
  let seatedComposition = null;
  let pixi = null;
  let mouth = 0;
  let palette = null;
  let pendingIntent = "neutral";
  let r21Reply = null;
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
  let motionTimer = null;
  let speaking = false;
  const counts = Object.create(null);
  const R21_MOTIONS = Object.freeze({
    neutral:"Neutral", playful:"Playful", excited:"Excited", curious:"Curious",
    tender:"Tender", reassuring:"Reassuring", serious:"Serious",
  });
  // Held poses are independent of the voice envelope and automatic blink.
  const R21_FACES = Object.freeze({
    neutral:     {mouth:.06,  mouthAtFullOpen:0,   browL:.04,  browR:.02,  caption:"Échange paisible"},
    playful:     {mouth:.40,  mouthAtFullOpen:.26, browL:.16, browR:.08, caption:"Petite malice"},
    excited:     {mouth:.56,  mouthAtFullOpen:.29, browL:.40,  browR:.36,  caption:"Élan enthousiaste"},
    curious:     {mouth:-.28, mouthAtFullOpen:0,   browL:.13,  browR:.13,  caption:"Attention intriguée"},
    tender:      {mouth:.23,  mouthAtFullOpen:.06, browL:-.06, browR:-.10, caption:"Douceur"},
    reassuring:  {mouth:.34,  mouthAtFullOpen:.16, browL:.09,  browR:.07,  caption:"Présence apaisante"},
    serious:     {mouth:-.74, browL:-.12, browR:-.12, caption:"Concentration tranquille"},
  });
  // Each row contains a parameter and its A/B offsets. A single offset is shared.
  // The brow accent in Playful A is already in its motion.
  const R21_ACTING = Object.freeze({
    neutral: {
      face: [
        ["ParamBrowLAngle", -.03],
        ["ParamBrowRAngle", -.02],
      ],
      posture: [["ParamBodyAngleX", .45, -.45]],
      aperture: [[.99, .99], [.98, .99]],
    },
    playful: {
      face: [
        ["ParamEyeBallX", -.10, .10],
        ["ParamBrowLAngle", -.23],
        ["ParamBrowRAngle", -.13],
        ["ParamBrowLY", 0, .16],
      ],
      posture: [["ParamBodyAngleZ", -2.4, 2.4]],
      aperture: [[.91, .97], [.97, .91]],
    },
    excited: {
      face: [
        ["ParamEyeBallY", .05],
        ["ParamBrowLAngle", -.19, -.14],
        ["ParamBrowRAngle", -.15, -.20],
      ],
      posture: [
        ["ParamBodyAngleZ", .65, -.65],
        ["ParamJadeIdleLean", .09, .06],
      ],
      aperture: [[1, 1], [1, 1]],
    },
    curious: {
      face: [
        ["ParamEyeBallX", .10, -.10],
        ["ParamBrowLY", .30, .04],
        ["ParamBrowRY", .04, .30],
        ["ParamBrowLAngle", -.19, .08],
        ["ParamBrowRAngle", .08, -.19],
      ],
      posture: [["ParamBodyAngleZ", -1.3, 1.3]],
      aperture: [[.99, .91], [.91, .99]],
    },
    tender: {
      face: [
        ["ParamEyeBallX", -.05, .05],
        ["ParamEyeBallY", -.10, -.06],
        ["ParamBrowLAngle", .11, .08],
        ["ParamBrowRAngle", .09, .11],
      ],
      posture: [["ParamBodyAngleZ", -.65, .75]],
      aperture: [[.87, .93], [.93, .89]],
    },
    reassuring: {
      face: [
        ["ParamEyeBallY", .02],
        ["ParamBrowLAngle", -.12, -.09],
        ["ParamBrowRAngle", -.09, -.12],
      ],
      posture: [["ParamBodyAngleX", .60, -.75]],
      aperture: [[.95, .96], [.96, .95]],
    },
    serious: {
      face: [
        ["ParamBrowLAngle", .16],
        ["ParamBrowRAngle", .14],
      ],
      posture: [["ParamBodyAngleX", .7, -.7]],
      aperture: [[.98, .98], [.98, .98]],
    },
  });
  // Signed lifts of the left and right ears, in seconds from the first expression.
  // Each gesture settles into a held pose until the reply fades.
  const R21_EAR_GESTURES = Object.freeze({
    neutral: {keys:[[.36,.13,.10], [.92,.03,.03]]},
    playful: {mirror:true, keys:[
      [.24,.40,-.10], [.50,.52,.20], [.85,-.13,.34], [1.24,.12,.02], [1.72,.05,-.06],
    ]},
    excited: {keys:[
      [.31,.53,.48], [.62,.19,.22], [.94,.59,.55], [1.40,.22,.25], [1.88,.13,.14],
    ]},
    curious: {mirror:true, keys:[
      [.29,.45,-.11], [.61,.48,-.23], [1.08,.27,-.17], [1.56,.19,-.12],
    ]},
    tender: {keys:[[.59,-.16,-.19], [1.20,-.26,-.23], [1.91,-.16,-.14]]},
    reassuring: {keys:[[.31,-.07,-.08], [.95,.24,.22], [1.52,.15,.14], [2.10,.07,.07]]},
    serious: {keys:[[.30,-.22,-.24], [.63,-.37,-.34], [1.01,-.17,-.17], [1.53,-.13,-.13]]},
  });
  const R21_EAR_BREATH = [
    {id:"ParamJadeEarFollowL", side:0, delayMs:130, gain:.34},
    {id:"ParamJadeEarFollowR", side:1, delayMs:185, gain:.30},
  ];
  const EAR_BREATH_REST = .43;
  const FACE_FADE_IN_MS = 140;
  const FACE_FADE_OUT_MS = 220;
  const FACE_AFTER_AUDIO_MS = 600;
  const FACE_TEXT_MS = 1500;
  const FORCE_MOTION = 3;
  const R21_MOTION_PARAMETERS = [
    "ParamAngleX", "ParamAngleY", "ParamAngleZ", "ParamBodyAngleX", "ParamBodyAngleZ",
    "ParamBreath", "ParamEyeBallX", "ParamEyeBallY", "ParamBrowLY", "ParamBrowRY",
    "ParamBrowLAngle", "ParamBrowRAngle", "ParamMouthForm", "ParamJadeEarTwitchL", "ParamJadeEarTwitchR",
    "ParamJadeIdleLean", "ParamJadeLegRelaxL", "ParamJadeLegRelaxR", "ParamJadeWeightShift",
  ];
  const SHAKE_DURATION = 1.05;

  function playMotion(group, index, priority) {
    try { model?.motion?.(group, index, priority)?.catch?.(() => {}); }
    catch (_) { /* The avatar remains usable if an optional motion fails. */ }
  }

  function loadMotion(group, index) {
    return model?.internalModel?.motionManager?.loadMotion?.(group, index)?.catch?.(() => null);
  }

  function canShake() {
    return activeProfile?.id === "next" && rendererState.status === "ready" &&
      renderRunning && onScreen && !document.hidden && permitsFraming();
  }

  function setShakeOffset(x, y) {
    const position = shakeLayer?.position;
    if (!position || (position.x === x && position.y === y)) return;
    position.set(x, y);
    notifyFraming();
  }

  function stopShake() {
    shakeImpulse = null;
    setShakeOffset(0, 0);
  }

  function nudgeFromShake(x, y) {
    if (!canShake() || !shakeLayer || !Number.isFinite(x) || !Number.isFinite(y) || (!x && !y)) return false;
    const layout = framingLayout();
    if (!layout) return false;
    const travel = Math.min(82, Math.min(layout.width * layout.cssX, layout.height * layout.cssY) * .19);
    shakeImpulse = {
      x:clamp(x, -1, 1), y:clamp(y, -1, 1), started:performance.now(),
      layout, travelX:travel / layout.cssX, travelY:.8 * travel / layout.cssY,
    };
    return true;
  }

  function shakeSpring(now) {
    const age = (now - shakeImpulse.started) / 1000;
    if (age >= SHAKE_DURATION || !canShake()) {
      stopShake();
      return 0;
    }
    return (1 - age / SHAKE_DURATION) ** 2 * Math.sin(27 * age);
  }

  function updateShakeLayer() {
    if (!shakeImpulse) return;
    const spring = shakeSpring(performance.now());
    if (!shakeImpulse) return;
    const {x, y, travelX, travelY, layout} = shakeImpulse;
    const shiftX = x * spring * travelX;
    const shiftY = y * spring * travelY;
    const correction = keepReachable(model.position.x + shiftX, model.position.y + shiftY, model.scale.x, layout);
    setShakeOffset(shiftX + correction.x, shiftY + correction.y);
  }

  function applyShake(core, now) {
    if (!shakeImpulse) return;
    const spring = shakeSpring(now);
    if (!shakeImpulse) return;
    // These angles drive hair and clothing in addition to the whole-avatar sway.
    const x = shakeImpulse.x * spring;
    const y = shakeImpulse.y * spring;
    core.addParameterValueById?.("ParamAngleX", 30 * x);
    core.addParameterValueById?.("ParamAngleY", 26 * y);
    core.addParameterValueById?.("ParamAngleZ", -22 * x);
    core.addParameterValueById?.("ParamBodyAngleX", 15 * x);
    core.addParameterValueById?.("ParamBodyAngleZ", -12 * x);
  }

  function easePose(progress) {
    return progress * progress * (3 - 2 * progress);
  }

  function replyPoseWeight(reply, now) {
    const progress = reply.fadeAt === null
      ? clamp((now - reply.preparedAt) / FACE_FADE_IN_MS, 0, 1)
      : clamp((reply.fadeAt + FACE_FADE_OUT_MS - now) / FACE_FADE_OUT_MS, 0, 1);
    return easePose(progress);
  }

  function profileSmileOpening(core, opening, mouthForm) {
    const yaw = Math.abs(core.getParameterValueById?.("ParamAngleX") ?? 0);
    const turn = easePose(clamp((yaw - 11) / 18, 0, 1));
    const smile = clamp(mouthForm / .26, 0, 1);
    // Preserve the articulation curve, with less aperture at a turned
    // smile's widest vowel. Small openings and straight-on views stay free.
    return opening * (1 - .18 * turn * smile * opening ** 2);
  }

  function earGestureAt(gesture, age, variant) {
    const keys = gesture.keys;
    const next = keys.findIndex(([time]) => time > age);
    const [fromTime, fromLeft, fromRight] = next === 0 ? [0,0,0] : keys.at(next < 0 ? -1 : next - 1);
    let left = fromLeft, right = fromRight;
    if (next >= 0) {
      const [toTime, toLeft, toRight] = keys[next];
      const weight = easePose(clamp((age - fromTime) / (toTime - fromTime), 0, 1));
      left += (toLeft - fromLeft) * weight;
      right += (toRight - fromRight) * weight;
    }
    return gesture.mirror && variant === 1 ? [right,left] : [left,right];
  }

  function applyActingOffsets(core, parameters, variant, weight) {
    for (const [id, a, b = a] of parameters) {
      core.addParameterValueById(id, variant === 0 ? a : b, weight);
    }
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
    // r21 leaves the eye curves free, so advance it during gestures as well.
    const blink = internal.eyeBlink;
    let lastBlinkUpdate = null;
    const hasParameter = id => !core.getParameterCount || core.getParameterIndex(id) < core.getParameterCount();
    const earResponses = typeof core.getParameterValueById === "function"
      ? R21_EAR_BREATH.filter(({id}) => hasParameter(id)).map(ear => ({...ear, breath:null}))
      : [];
    const hasBreath = earResponses.length > 0 && hasParameter("ParamBreath");
    let lastEarUpdate = null;
    const updateMotionEffects = () => {
      const now = performance.now();
      const delta = lastBlinkUpdate === null ? 0 : Math.min(.1, (now - lastBlinkUpdate) / 1000);
      lastBlinkUpdate = now;
      blink?.updateParameters(core, delta);
      if (r21Reply?.acting) {
        // Apply the posture before physics so hair, clothes and arms follow it.
        applyActingOffsets(core, r21Reply.acting.posture, r21Reply.index, replyPoseWeight(r21Reply, now));
      }
      applyShake(core, now);
    };
    const updateFace = () => {
      const now = performance.now();
      const weight = r21Reply ? replyPoseWeight(r21Reply, now) : 0;
      let opening = mouth;
      if (earResponses.length) {
        // Read the same breath as the chest, after the SDK and physics. The
        // SDK restores parameters after drawing, so these offsets never stack.
        const breath = hasBreath ? core.getParameterValueById("ParamBreath") : EAR_BREATH_REST;
        const elapsed = lastEarUpdate === null ? 0 : clamp(now - lastEarUpdate, 0, 100);
        lastEarUpdate = now;
        const gesture = r21Reply
          ? earGestureAt(r21Reply.ears, (now - r21Reply.preparedAt) / 1000, r21Reply.index)
          : null;
        for (const ear of earResponses) {
          ear.breath ??= breath;
          ear.breath += (breath - ear.breath) * -Math.expm1(-elapsed / ear.delayMs);
          const physicalFollow = core.getParameterValueById(ear.id);
          const lift = (ear.breath - EAR_BREATH_REST) * ear.gain + (gesture?.[ear.side] ?? 0) * weight;
          // Reserve room for the head follow, even at the peak of an accent.
          core.addParameterValueById(ear.id, lift * (1 - Math.abs(physicalFollow)));
        }
      }
      if (r21Reply) {
        const {pose, acting, index} = r21Reply;
        const openForm = pose.mouthAtFullOpen ?? pose.mouth;
        const mouthForm = pose.mouth + (openForm - pose.mouth) * mouth;
        core.setParameterValueById("ParamMouthForm", mouthForm, weight);
        opening = profileSmileOpening(core, mouth, mouthForm * weight);
        core.addParameterValueById("ParamBrowLY", pose.browL, weight);
        core.addParameterValueById("ParamBrowRY", pose.browR, weight);
        if (acting) {
          applyActingOffsets(core, acting.face, index, weight);
          const [left, right] = acting.aperture[index];
          // Scale the aperture after blinking. A fully closed lid stays closed.
          core.multiplyParameterValueById("ParamEyeLOpen", left, weight);
          core.multiplyParameterValueById("ParamEyeROpen", right, weight);
        }
      }
      core.setParameterValueById("ParamMouthOpenY", opening);
    };
    internal.eyeBlink = undefined;
    internal.on?.("beforeMotionUpdate", resetMotionParameters);
    internal.on?.("afterMotionUpdate", updateMotionEffects);
    internal.on?.("beforeModelUpdate", updateFace);
    manager?.on?.("motionLoaded", onMotionLoaded);
    return () => {
      internal.off?.("beforeMotionUpdate", resetMotionParameters);
      internal.off?.("afterMotionUpdate", updateMotionEffects);
      internal.off?.("beforeModelUpdate", updateFace);
      manager?.off?.("motionLoaded", onMotionLoaded);
    };
  }

  function applyExpression(expression) {
    if (!model || activeProfile?.id === "next" || !activeProfile?.classicIntents) return;
    try {
      if (expression === "Neutral") {
        model.internalModel?.motionManager?.expressionManager?.resetExpression?.();
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

  function clearReplyTimers() {
    if (resetTimer !== null) clearTimeout(resetTimer);
    if (motionTimer !== null) clearTimeout(motionTimer);
    resetTimer = motionTimer = null;
  }

  function returnToIdle() {
    clearReplyTimers();
    pendingIntent = "neutral";
    r21Reply = null;
    mood.textContent = "Jade est attentive.";
    applyExpression("Neutral");
  }

  function stopReplyMotion() {
    const state = model?.internalModel?.motionManager?.state;
    if (r21Reply && state?.isActive?.(r21Reply.group, r21Reply.index)) {
      playMotion(activeProfile.idleMotion, 0, FORCE_MOTION);
    }
  }

  function startReplyMotion(delayMs = 0) {
    const reply = r21Reply;
    if (!reply || reply.motionStarted || motionTimer !== null) return;
    const start = () => {
      motionTimer = null;
      if (r21Reply !== reply) return;
      reply.motionStarted = true;
      if (reply.motionReady) {
        // Reserving a motion in the SDK before its download ends can leave
        // a delayed gesture queued behind an Idle that is already playing.
        void reply.motionReady.then(motion => {
          if (motion && r21Reply === reply && reply.fadeAt === null)
            playMotion(reply.group, reply.index, FORCE_MOTION);
        });
      } else {
        playMotion(reply.group, reply.index, FORCE_MOTION);
      }
    };
    if (delayMs > 0) motionTimer = setTimeout(start, delayMs);
    else start();
  }

  function finishReply(hadAudio) {
    const reply = r21Reply;
    if (!reply || resetTimer !== null) return;
    startReplyMotion();
    const hold = hadAudio ? FACE_AFTER_AUDIO_MS : FACE_TEXT_MS;
    resetTimer = setTimeout(() => {
      if (r21Reply !== reply) return;
      reply.fadeAt = performance.now();
      stopReplyMotion();
      resetTimer = setTimeout(returnToIdle, FACE_FADE_OUT_MS);
    }, hold);
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
      if (resumeFromPause) {
        if (!r21Reply) returnToIdle();
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
      speaking = Boolean(value);
      if (activeProfile?.id !== "next" && !speaking && pendingIntent !== "neutral") returnToIdle();
    },
    startReplyMotion, finishReply,
    resetIntent() {
      stopReplyMotion();
      returnToIdle();
    },
    setIntent(label, {deferMotion = false} = {}) {
      pendingIntent = label;
      if (!palette?.enabled) return;
      const key = Object.hasOwn(palette.intents, label) ? label : "neutral";
      const reactions = palette.intents[key];
      if (!Array.isArray(reactions) || !reactions.length) return;
      const r21 = activeProfile?.id === "next";
      const index = r21 ? Math.floor(Math.random() * 2) : (counts[key] || 0);
      if (!r21) counts[key] = index + 1;
      const choice = reactions[index % reactions.length];
      if (!choice || typeof choice.text !== "string") return;
      clearReplyTimers();
      if (r21) {
        const pose = R21_FACES[key], group = R21_MOTIONS[key];
        r21Reply = {pose, group, index, acting:R21_ACTING[key], ears:R21_EAR_GESTURES[key],
          preparedAt:performance.now(), fadeAt:null, motionStarted:false,
          motionReady:loadMotion(group, index)};
        mood.textContent = pose.caption;
        if (!deferMotion) startReplyMotion();
        return true;
      }
      mood.textContent = choice.text;
      applyExpression(choice.expression);
      resetTimer = setTimeout(() => { if (!speaking) returnToIdle(); }, 12000);
      return false;
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

  function keepReachable(x, y, scale, layout) {
    // A bounding box could leave only an empty corner on screen. Keep a solid part within reach.
    const insetX = Math.min(30, layout.width / 2);
    const insetY = Math.min(30, layout.height / 2);
    const correction = {x:0, y:0};
    let nearest = Infinity;
    for (const [anchorX, anchorY] of R21_GRAB_AREAS) {
      const px = x + (anchorX - .5) * standingCamera.width * scale;
      const py = y + (anchorY - .5) * standingCamera.height * scale;
      const dx = clamp(px, layout.left + insetX, layout.right - insetX) - px;
      const dy = clamp(py, layout.top + insetY, layout.bottom - insetY) - py;
      const distance = Math.hypot(dx, dy);
      if (distance < nearest) {
        nearest = distance;
        correction.x = dx;
        correction.y = dy;
      }
    }
    return correction;
  }

  function applyFraming(layout, commit = false) {
    const base = standingCamera;
    let {x, y, scale} = base;
    if (layout && (framing.x || framing.y || framing.zoom !== 1)) {
      x += framing.x * layout.width;
      y += framing.y * layout.height;
      scale *= framing.zoom;
      const correction = keepReachable(x, y, scale, layout);
      x += correction.x;
      y += correction.y;
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
    const x = model.position.x + (shakeLayer?.position.x ?? 0);
    const y = model.position.y + (shakeLayer?.position.y ?? 0);
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
    const x = ((clientX - layout.canvas.left) / layout.cssX - model.position.x - (shakeLayer?.position.x ?? 0))
      / (standingCamera.width * scale);
    const y = ((clientY - layout.canvas.top) / layout.cssY - model.position.y - (shakeLayer?.position.y ?? 0))
      / (standingCamera.height * scale);
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
    const shownX = model.position.x + (shakeLayer?.position.x ?? 0);
    const shownY = model.position.y + (shakeLayer?.position.y ?? 0);
    stopShake();
    framing.x = (shownX - standingCamera.x + dx / layout.cssX) / layout.width;
    framing.y = (shownY - standingCamera.y + dy / layout.cssY) / layout.height;
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
    const shownX = model.position.x + (shakeLayer?.position.x ?? 0);
    const shownY = model.position.y + (shakeLayer?.position.y ?? 0);
    stopShake();
    const x = (clientX - layout.canvas.left) / layout.cssX;
    const y = (clientY - layout.canvas.top) / layout.cssY;
    framing.x = (x + (shownX - x) * ratio - standingCamera.x) / layout.width;
    framing.y = (y + (shownY - y) * ratio - standingCamera.y) / layout.height;
    framing.zoom = zoom;
    applyFraming(layout, true);
    return true;
  }

  function resetView() {
    if (!activeFramingLayout()) return false;
    stopShake();
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
    stopShake();
    const width = Math.max(1, target.clientWidth);
    const height = Math.max(1, target.clientHeight);
    pixi.renderer.resize(width, height);
    const naturalWidth = Math.max(model.width / (model.scale.x || 1), 1);
    const naturalHeight = Math.max(model.height / (model.scale.y || 1), 1);
    const r21 = activeProfile?.id === "next";
    const standingBedroom = r21 && room?.dataset.room === "bedroom";
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
    if (shakeLayer) {
      attempt(() => shakeLayer.destroy());
      shakeLayer = null;
    }
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
    // Update the transient transform before Pixi derives world transforms for drawing.
    pixi.ticker.add(updateShakeLayer, undefined, PIXI.UPDATE_PRIORITY?.NORMAL ?? 0);
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
    if (profile.id === "next") {
      shakeLayer = new window.PIXI.Container();
      shakeLayer.addChild(model);
      pixi.stage.addChild(shakeLayer);
    } else {
      pixi.stage.addChild(model);
    }
    resize();
    fallback.classList.add("hidden");
    if (typeof Event === "function") room?.dispatchEvent?.(new Event("jade-avatar-ready"));
    if (profile.id === "next") releaseMotionBindings = bindR21MotionPlayback(next.internalModel, profile.idleMotion);
    if (profile.idleMotion) playMotion(profile.idleMotion, 0,
      profile.id === "next" ? window.PIXI?.live2d?.MotionPriority?.IDLE ?? 1 : undefined);
    if (profile.id === "next") {
      // Warm the reply clips without holding up model display or audio.
      for (const group of Object.values(R21_MOTIONS)) {
        loadMotion(group, 0);
        loadMotion(group, 1);
      }
    }
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
