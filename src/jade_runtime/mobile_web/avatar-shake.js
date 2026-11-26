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
  const AXES = ["x", "y", "z"];
  const PEAK_THRESHOLD = 7.5;
  const MIN_REVERSAL_MS = 20;
  const MAX_REVERSAL_MS = 400;
  const COOLDOWN_MS = 850;
  let enabled = false;
  let listening = false;
  let permissionAttempt = 0;
  let gravity = [null, null, null];
  let lastRawTime = null;
  let peak = null;
  let nextShakeAt = 0;
  let sampleTimer = null;
  let receivedMotion = false;

  function report(message) {
    if (status && status.textContent !== message) status.textContent = message;
  }

  function inScene() {
    return !document.hidden && (shell.dataset.view === "home" || shell.classList.contains("is-room-only")) &&
      window.JadeAvatar?.state?.modelId === "next" && window.JadeAvatar.state.status === "ready";
  }

  function resetMovement() {
    gravity = [null, null, null];
    lastRawTime = null;
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
      receivedMotion = false;
      report("En attente des données du capteur de mouvement…");
      window.addEventListener("devicemotion", readMotion, {passive:true});
      sampleTimer = window.setTimeout(() => {
        sampleTimer = null;
        report("Aucune donnée de mouvement reçue. Vérifie « Capteurs de mouvement » dans les autorisations du site.");
      }, 2500);
    } else {
      window.removeEventListener("devicemotion", readMotion);
      clearSampleTimer();
      resetMovement();
    }
  }

  function vector(sample) {
    return AXES.map(axis => Number.isFinite(sample?.[axis]) ? sample[axis] : null);
  }

  function linearAcceleration(event, now) {
    const linear = vector(event.acceleration);
    const raw = vector(event.accelerationIncludingGravity);
    const elapsed = lastRawTime === null ? 0 : Math.max(0, Math.min(250, now - lastRawTime));
    const smoothing = Math.min(.18, elapsed / (550 + elapsed));
    const corrected = raw.map((axis, index) => {
      if (axis === null) return null;
      const previous = gravity[index] ?? axis;
      // Smooth gravity slowly even when sensor events arrive at irregular intervals.
      gravity[index] = previous + (axis - previous) * smoothing;
      return axis - gravity[index];
    });
    if (raw.some(axis => axis !== null)) lastRawTime = now;
    const combined = linear.map((axis, index) => axis ?? corrected[index]);
    if (combined.every(axis => axis === null)) return null;
    const motion = combined.map(axis => axis ?? 0);
    // Prefer a raw peak when the linear channel stays near zero.
    if (Math.hypot(...motion) < 2) {
      const fallback = corrected.map(axis => axis ?? 0);
      if (Math.hypot(...fallback) >= PEAK_THRESHOLD) return fallback;
    }
    return motion;
  }

  function readMotion(event) {
    if (!inScene() || reducedMotion?.matches) {
      sync();
      return;
    }
    const now = event.timeStamp;
    if (!Number.isFinite(now)) return;
    const acceleration = linearAcceleration(event, now);
    if (!acceleration) return;
    if (!receivedMotion) {
      receivedMotion = true;
      clearSampleTimer();
      report("Capteur de mouvement actif. Secoue le téléphone sur l’Accueil ou en plein écran.");
    }
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
    const intensity = Math.min(1, Math.max(magnitude, peak.magnitude) / 12);
    peak = null;

    const angle = (window.screen?.orientation?.angle ?? window.orientation ?? 0) * Math.PI / 180;
    const horizontal = x * Math.cos(angle) - y * Math.sin(angle);
    const vertical = Math.hypot(x, y) > magnitude * .35
      ? x * Math.sin(angle) + y * Math.cos(angle) : z * .65;
    if (window.JadeAvatar?.nudgeFromShake?.(horizontal * intensity / magnitude, vertical * intensity / magnitude)) {
      nextShakeAt = now + COOLDOWN_MS;
      report("Secousse détectée.");
    }
  }

  control.checked = false;
  control.disabled = !supported;
  report(supported ? "Active le réglage, puis retourne à l’Accueil ou passe en plein écran."
    : "Capteur de mouvement indisponible.");
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
