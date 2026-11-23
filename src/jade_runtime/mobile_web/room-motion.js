"use strict";
(() => {
  const scene = document.querySelector(".room-art");
  const room = document.querySelector(".room");
  const roomSelect = document.getElementById("room-selector");
  if (!scene || !roomSelect) return;
  // The room selection works even when container query units are unavailable.
  const supportsRoomLayers = typeof CSS !== "undefined" && CSS.supports("width", "1cqh");

  const backdrop = scene.querySelector(".room-plane > img");
  const curtain = scene.querySelector(".room-curtain");
  const left = scene.querySelector(".room-shadow-left");
  const right = scene.querySelector(".room-shadow-right");
  const steam = scene.querySelector(".room-steam");
  const reflection = scene.querySelector(".room-reflection");
  const kitchenEffects = scene.querySelector(".kitchen-effects");
  if (![backdrop, curtain, left, right, steam, reflection].every(Boolean)) return;

  const original = backdrop.getAttribute("src");
  const ROOM_IMAGES = Object.freeze({
    bedroom: original,
    kitchen: "/assets/room-kitchen.webp",
  });
  const requested = new URLSearchParams(window.location.search).get("room");
  let activeRoom = Object.prototype.hasOwnProperty.call(ROOM_IMAGES, requested) ? requested : "bedroom";
  let selectionRevision = 0;
  scene.dataset.room = activeRoom;
  if (room) room.dataset.room = activeRoom;
  roomSelect.value = activeRoom;
  const preference = matchMedia("(prefers-reduced-motion: reduce)");
  const movingLayers = [curtain, left, right, steam];
  const optionalLayers = [...movingLayers, reflection];
  let ready = false;
  let visible = true;
  let frame = null;
  let elapsed = 0;
  let lastTime = null;
  let lastPaint = -Infinity;

  function windAt(seconds) {
    // A coherent breeze, with three incommensurate periods and a slow gust
    // envelope. This avoids synchronized loops and abrupt direction changes.
    const gust = 0.76 + 0.24 * Math.sin(0.19 * seconds + 0.8);
    return gust * (
      0.57 * Math.sin(0.43 * seconds + 0.4) +
      0.29 * Math.sin(0.88 * seconds + 1.3) +
      0.14 * Math.sin(1.51 * seconds + 2.1)
    );
  }

  function animate(seconds) {
    const wind = windAt(seconds);
    const flutter = 0.7 * Math.sin(1.93 * seconds + 0.9);
    // All motion applies to isolated RGBA textures. The fixed frame and
    // painted room never move or become the source of a warped rectangle.
    curtain.style.transform = "translate3d(" + (5.5 * wind).toFixed(2) + "%, 0, 0) rotate(" +
      (7.6 * wind + flutter).toFixed(2) + "deg) skewX(" + (4.2 * wind).toFixed(2) + "deg)";
    left.style.transform = "translate3d(" + (11 * wind).toFixed(2) + "%, " +
      (4.2 * wind).toFixed(2) + "%, 0) rotate(" + (2.7 * wind).toFixed(2) + "deg)";
    right.style.transform = "translate3d(" + (14 * wind).toFixed(2) + "%, " +
      (-3.7 * wind).toFixed(2) + "%, 0) rotate(" + (-3.1 * wind).toFixed(2) + "deg)";
    steam.style.transform = "translate3d(" + (15 * wind).toFixed(2) + "%, 0, 0)";
    left.style.opacity = (0.87 + 0.13 * Math.sin(seconds * 0.41 + 1)).toFixed(3);
    right.style.opacity = (0.87 + 0.13 * Math.sin(seconds * 0.33 + 2)).toFixed(3);
  }

  function paint(time) {
    if (lastTime === null) lastTime = time;
    elapsed += Math.max(0, Math.min(50, time - lastTime));
    lastTime = time;
    // At most 30 DOM updates/s on 60/90/120 Hz phones. rAF still follows
    // the browser refresh rate so the browser controls scheduling.
    if (time - lastPaint >= 33) {
      animate(elapsed / 1000);
      lastPaint = time;
    }
    frame = requestAnimationFrame(paint);
  }

  function sync() {
    const reduced = preference.matches;
    // Bedroom retains the rAF renderer. Kitchen owns independent CSS-only accents.
    const bedroomLayers = activeRoom === "bedroom" &&
      room?.dataset.seatedReady !== "true" && supportsRoomLayers && ready && !reduced;
    const kitchenLayers = activeRoom === "kitchen" && supportsRoomLayers && !reduced;
    const source = activeRoom === "kitchen"
      ? ROOM_IMAGES.kitchen
      : (bedroomLayers ? "/assets/room-backdrop.webp" : original);
    if (backdrop.getAttribute("src") !== source) backdrop.src = source;
    for (const layer of optionalLayers) layer.hidden = !bedroomLayers;
    if (kitchenEffects) kitchenEffects.hidden = !kitchenLayers;

    const running = bedroomLayers && visible && !document.hidden;
    const kitchenRunning = kitchenLayers && visible && !document.hidden;
    scene.toggleAttribute("data-paused", !(running || kitchenRunning));
    if (running && frame === null) {
      frame = requestAnimationFrame(paint);
    } else if (!running) {
      if (frame !== null) cancelAnimationFrame(frame);
      frame = null;
      lastTime = null;
      lastPaint = -Infinity;
      for (const layer of movingLayers) {
        layer.style.transform = "";
        layer.style.opacity = "";
      }
    }
  }

  async function loadLayer(path) {
    const image = new Image();
    image.src = path;
    await image.decode();
    if (!image.naturalWidth || !image.naturalHeight) throw Error("room layer unavailable");
    return image;
  }

  // Room images are preloaded before a user-visible change to avoid flashes.
  // No storage of credentials or other private data in the browser.
  async function changeRoom(next) {
    if (!Object.prototype.hasOwnProperty.call(ROOM_IMAGES, next)) return;
    const revision = ++selectionRevision;
    const image = new Image();
    try {
      image.src = ROOM_IMAGES[next];
      await image.decode();
      if (!image.naturalWidth || !image.naturalHeight) throw Error("room image unavailable");
    } catch (_) {
      if (revision === selectionRevision) roomSelect.value = activeRoom;
      return;
    }
    if (revision !== selectionRevision) return;
    activeRoom = next;
    scene.dataset.room = next;
    if (room) room.dataset.room = next;
    roomSelect.value = next;
    room?.dispatchEvent?.(new Event("jade-room-changed"));
    sync();
    const url = new URL(window.location.href);
    if (next === "bedroom") url.searchParams.delete("room");
    else url.searchParams.set("room", next);
    window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
  }
  roomSelect.addEventListener("change", () => { void changeRoom(roomSelect.value); });
  room?.addEventListener("jade-seated-ready", sync);

  if (supportsRoomLayers) {
    Promise.all([
      loadLayer("/assets/room-backdrop.webp"),
      loadLayer("/assets/room-curtain.webp"),
    ]).then(([, fabric]) => {
      // An asset finishing loading does not change the selected room.
      curtain.src = fabric.src;
      ready = true;
      sync();
    }).catch(() => {
      // Never expose a half-assembled bedroom. Use its original composite.
      ready = false;
      sync();
    });
  }

  document.addEventListener("visibilitychange", sync);
  if (typeof preference.addEventListener === "function") preference.addEventListener("change", sync);
  else preference.addListener(sync);
  if (typeof IntersectionObserver === "function") {
    new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      sync();
    }).observe(scene);
  }
  sync();
})();
