(() => {
  "use strict";

  const control = document.getElementById("avatar-shake-enabled");
  const status = document.getElementById("avatar-shake-status");
  const shell = document.querySelector(".shell");
  const room = document.querySelector(".room");
  if (!control || !shell || !room) return;

  const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)");
  const motionAPI = window.DeviceMotionEvent;
  const supported = Boolean(motionAPI) && window.isSecureContext;
  const PEAK_THRESHOLD = 11;
  const MIN_REVERSAL_MS = 45;
  const MAX_REVERSAL_MS = 300;
  const COOLDOWN_MS = 850;
  let enabled = false;
  let listening = false;
  let permissionAttempt = 0;
  let gravity = null;
  let peak = null;
  let nextShakeAt = 0;
  let sampleTimer = null;

  function report(message) {
    if (status && status.textContent !== message) status.textContent = message;
  }

  function inScene() {
    return !document.hidden && (shell.dataset.view === "home" || shell.classList.contains("is-room-only")) &&
      window.JadeAvatar?.state?.modelId === "next" && window.JadeAvatar.state.status === "ready";
  }

  function resetMovement() {
    gravity = null;
    peak = null;
    nextShakeAt = 0;
    window.JadeAvatar?.stopShake?.();
  }

  function clearSampleTimer() {
    if (sampleTimer !== null) window.clearTimeout(sampleTimer);
    sampleTimer = null;
  }

  function sync() {
    const shouldListen = enabled && !reducedMotion?.matches && inScene();
    if (shouldListen === listening) return;
    listening = shouldListen;
    if (listening) {
      window.addEventListener("devicemotion", readMotion, {passive:true});
      sampleTimer = window.setTimeout(() => {
        sampleTimer = null;
        report("Aucune donnée de mouvement reçue.");
      }, 2500);
    } else {
      window.removeEventListener("devicemotion", readMotion);
      clearSampleTimer();
      resetMovement();
    }
  }

  function vector(sample) {
    if (!sample || ![sample.x, sample.y, sample.z].every(Number.isFinite)) return null;
    return [sample.x, sample.y, sample.z];
  }

  function linearAcceleration(event) {
    const linear = vector(event.acceleration);
    if (linear) return linear;
    const raw = vector(event.accelerationIncludingGravity);
    if (!raw) return null;
    // Fall back to a low-pass estimate of gravity on devices with no linear signal.
    gravity = gravity ? gravity.map((axis, index) => .8 * axis + .2 * raw[index]) : raw;
    return raw.map((axis, index) => axis - gravity[index]);
  }

  function readMotion(event) {
    if (!inScene() || reducedMotion?.matches) {
      sync();
      return;
    }
    const acceleration = linearAcceleration(event);
    if (!acceleration) return;
    clearSampleTimer();
    report("Réaction aux secousses activée.");
    const now = event.timeStamp;
    if (now < nextShakeAt) return;
    const [x, y, z] = acceleration;
    const magnitude = Math.hypot(x, y, z);
    if (magnitude < PEAK_THRESHOLD) return;

    // A deliberate shake reverses direction quickly. Ignore single jolts and slow orientation changes.
    const elapsed = peak ? now - peak.time : Infinity;
    if (elapsed > MAX_REVERSAL_MS) {
      peak = {x, y, z, magnitude, time:now};
      return;
    }
    const alignment = (x * peak.x + y * peak.y + z * peak.z) / (magnitude * peak.magnitude);
    if (elapsed < MIN_REVERSAL_MS || alignment > -.35) return;
    peak = null;

    const angle = (window.screen?.orientation?.angle ?? window.orientation ?? 0) * Math.PI / 180;
    const horizontal = x * Math.cos(angle) - y * Math.sin(angle);
    const vertical = Math.hypot(x, y) > magnitude * .35
      ? x * Math.sin(angle) + y * Math.cos(angle) : z * .65;
    if (window.JadeAvatar?.nudgeFromShake?.(horizontal / 18, vertical / 18)) nextShakeAt = now + COOLDOWN_MS;
  }

  control.checked = false;
  control.disabled = !supported;
  if (!supported) report("Capteur de mouvement indisponible.");
  control.addEventListener("change", async () => {
    const attempt = ++permissionAttempt;
    enabled = false;
    sync();
    if (!control.checked) {
      report("Réaction aux secousses désactivée.");
      return;
    }
    let granted = supported;
    if (supported && typeof motionAPI.requestPermission === "function") {
      report("Autorisation du capteur de mouvement…");
      try { granted = await motionAPI.requestPermission() === "granted"; }
      catch (_) { granted = false; }
    }
    if (attempt !== permissionAttempt) return;
    if (!granted) {
      control.checked = false;
      report("Accès au capteur de mouvement refusé ou indisponible.");
      return;
    }
    enabled = true;
    onReducedMotionChange();
  });

  function onReducedMotionChange() {
    if (enabled) report(reducedMotion?.matches
      ? "Effet en pause selon la préférence de mouvement réduit."
      : "Réaction aux secousses activée. Essaie dans l’Accueil ou en plein écran.");
    sync();
  }

  reducedMotion?.addEventListener?.("change", onReducedMotionChange);
  window.screen?.orientation?.addEventListener?.("change", resetMovement);
  window.addEventListener("orientationchange", resetMovement);
  document.addEventListener("visibilitychange", sync);
  document.addEventListener("fullscreenchange", sync);
  room.addEventListener("jade-avatar-state", sync);
  room.addEventListener("jade-avatar-framing", sync);
  room.addEventListener("jade-room-changed", resetMovement);
})();
