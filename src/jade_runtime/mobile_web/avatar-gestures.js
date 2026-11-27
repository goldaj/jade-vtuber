(() => {
  "use strict";

  const room = document.querySelector(".room");
  const shell = document.querySelector(".shell");
  const zone = document.getElementById("avatar-touch-zone");
  const recenter = document.getElementById("avatar-recenter");
  if (!room || !shell || !zone || !recenter) return;

  const HOLD_MS = 1200;
  const HOLD_SLOP = 10;
  const PINCH_MARGIN = 16;
  const pointers = new Map();
  const handledEvents = new WeakSet();
  let holdTimer = null;
  let mode = null;
  let lastRelease = null;
  let layout = null;
  let syncQueued = false;

  const renderer = () => window.JadeAvatar;
  const inScene = () => shell.dataset.view === "home" || shell.classList.contains("is-room-only");
  function ready() {
    const state = renderer()?.state;
    return !document.hidden && inScene() && state?.modelId === "next" && state.status === "ready";
  }

  function stopHold() {
    if (holdTimer !== null) window.clearTimeout(holdTimer);
    holdTimer = null;
  }

  function stopGesture() {
    stopHold();
    const captured = [...pointers.keys()];
    pointers.clear();
    mode = null;
    zone.classList.remove("is-grabbed");
    for (const id of captured) {
      if (zone.hasPointerCapture?.(id)) zone.releasePointerCapture(id);
    }
  }

  function syncFrame() {
    const current = `${shell.dataset.view}:${shell.classList.contains("is-room-only")}:${room.dataset.room}`;
    const available = ready();
    if (current !== layout || !available) stopGesture();
    layout = current;

    recenter.hidden = !available;
    const frame = available && renderer().getTouchFrame();
    zone.hidden = !frame;
    if (!frame) return;

    // Leave room for a second finger just outside Jade's visible silhouette.
    // The long press still checks the model itself before starting.
    const rect = room.getBoundingClientRect();
    const x = rect.left + room.clientLeft;
    const y = rect.top + room.clientTop;
    const left = Math.max(0, frame.left - x - PINCH_MARGIN);
    const top = Math.max(0, frame.top - y - PINCH_MARGIN);
    const right = Math.min(room.clientWidth, frame.right - x + PINCH_MARGIN);
    const bottom = Math.min(room.clientHeight, frame.bottom - y + PINCH_MARGIN);
    Object.assign(zone.style, {left:`${left}px`, top:`${top}px`,
      width:`${Math.max(0, right - left)}px`, height:`${Math.max(0, bottom - top)}px`});
  }

  function queueSync() {
    if (syncQueued) return;
    syncQueued = true;
    window.requestAnimationFrame(() => {
      syncQueued = false;
      syncFrame();
    });
  }

  function consume(event) {
    handledEvents.add(event);
    event.preventDefault();
  }

  function markRelease(event) {
    consume(event);
    lastRelease = {time:event.timeStamp, x:event.clientX, y:event.clientY};
  }

  function isCompatibilityTap(event) {
    if (!lastRelease || event.pointerType === "mouse" || event.sourceCapabilities?.firesTouchEvents === false)
      return false;
    return zone.contains(event.target) && event.timeStamp >= lastRelease.time
      && event.timeStamp - lastRelease.time < 450
      && Math.hypot(event.clientX - lastRelease.x, event.clientY - lastRelease.y) <= 24;
  }

  window.JadeAvatarGestures = {
    shouldIgnoreFullscreenTap(event) {
      return handledEvents.has(event) || (event.type === "dblclick" && isCompatibilityTap(event));
    }
  };

  function pinchGeometry() {
    const [first, second] = pointers.values();
    return {x:(first.x + second.x) / 2, y:(first.y + second.y) / 2,
      span:Math.hypot(first.x - second.x, first.y - second.y)};
  }

  function move(point, event) {
    const dx = event.clientX - point.x;
    const dy = event.clientY - point.y;
    if (!dx && !dy) return;
    const before = mode === "pinch" ? pinchGeometry() : null;
    point.x = event.clientX;
    point.y = event.clientY;
    if (mode === "drag") {
      renderer().moveView(dx, dy);
    } else if (before) {
      const after = pinchGeometry();
      if (before.span >= 2 && after.span >= 2) renderer().zoomView(after.span / before.span, before.x, before.y);
      renderer().moveView(after.x - before.x, after.y - before.y);
    } else if (Math.hypot(point.x - point.startX, point.y - point.startY) > HOLD_SLOP) {
      stopHold();
    }
  }

  // Claim touches on Jade before the browser or WebView starts its native
  // long press. Pointer events still drive dragging, pinching and double taps.
  zone.addEventListener("touchstart", event => {
    if (!event.cancelable || zone.hidden || !ready()) return;
    for (const touch of event.changedTouches) {
      if (renderer().isModelAt(touch.clientX, touch.clientY)) {
        event.preventDefault();
        return;
      }
    }
  }, {passive:false});

  zone.addEventListener("pointerdown", event => {
    if (event.pointerType !== "touch" || !ready() || zone.hidden || (!pointers.size && event.isPrimary === false))
      return;
    const {clientX:x, clientY:y, pointerId:id} = event;
    const point = {x, y, startX:x, startY:y, onModel:renderer().isModelAt(x, y)};
    pointers.set(id, point);
    zone.setPointerCapture?.(id);
    if (pointers.size === 1 && point.onModel) {
      holdTimer = window.setTimeout(() => {
        holdTimer = null;
        if (!ready() || !pointers.has(id) || !renderer().isModelAt(point.x, point.y)) return;
        mode = "drag";
        zone.classList.add("is-grabbed");
        navigator.vibrate?.(20);
      }, HOLD_MS);
    } else if (pointers.size >= 2) {
      stopHold();
      zone.classList.remove("is-grabbed");
      if (pointers.size === 2 && mode !== "settled" && [...pointers.values()].some(touch => touch.onModel))
        mode = "pinch";
      else
        mode = "settled";
      consume(event);
    }
  });

  zone.addEventListener("pointermove", event => {
    const point = pointers.get(event.pointerId);
    if (!point) return;
    if (!ready()) return stopGesture();
    move(point, event);
    if (mode) consume(event);
  });

  zone.addEventListener("pointerup", event => {
    const point = pointers.get(event.pointerId);
    if (!point) return;
    if (mode) {
      if (ready()) move(point, event);
      markRelease(event);
    }
    stopHold();
    pointers.delete(event.pointerId);
    mode = pointers.size ? "settled" : null;
    zone.classList.remove("is-grabbed");
  });

  for (const type of ["pointercancel", "lostpointercapture"]) {
    zone.addEventListener(type, event => {
      if (pointers.has(event.pointerId)) stopGesture();
    });
  }

  zone.addEventListener("contextmenu", event => {
    if (holdTimer !== null || mode || isCompatibilityTap(event)) event.preventDefault();
  });
  zone.addEventListener("click", event => {
    if (isCompatibilityTap(event)) consume(event);
  });
  recenter.addEventListener("click", () => {
    stopGesture();
    if (ready()) renderer().resetView();
  });
  document.addEventListener("pointerdown", event => {
    if (event.pointerType === "touch" && !zone.contains(event.target)) stopGesture();
  }, true);

  function layoutChanged() {
    stopGesture();
    queueSync();
  }

  room.addEventListener("jade-avatar-framing", queueSync);
  room.addEventListener("jade-avatar-state", layoutChanged);
  room.addEventListener("jade-room-changed", layoutChanged);
  document.addEventListener("fullscreenchange", layoutChanged);
  document.addEventListener("visibilitychange", layoutChanged);
  window.addEventListener("resize", layoutChanged);
  window.addEventListener("blur", stopGesture);
  new ResizeObserver(layoutChanged).observe(room);
  syncFrame();
})();
