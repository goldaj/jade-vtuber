"use strict";
(() => {
  const scene = document.querySelector(".room-art");
  if (!scene || !CSS.supports("width", "1cqh")) return;

  const backdrop = scene.querySelector(".room-plane > img");
  const curtain = scene.querySelector(".room-curtain");
  const left = scene.querySelector(".room-shadow-left");
  const right = scene.querySelector(".room-shadow-right");
  const steam = scene.querySelector(".room-steam");
  const reflection = scene.querySelector(".room-reflection");
  if (![backdrop, curtain, left, right, steam, reflection].every(Boolean)) return;

  const original = backdrop.getAttribute("src");
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
    backdrop.src = ready && !reduced ? "/assets/room-backdrop.webp" : original;
    for (const layer of optionalLayers) layer.hidden = !ready || reduced;

    const running = ready && visible && !document.hidden && !reduced;
    scene.toggleAttribute("data-paused", !running);
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

  Promise.all([
    loadLayer("/assets/room-backdrop.webp"),
    loadLayer("/assets/room-curtain.webp"),
  ]).then(([clean, fabric]) => {
    backdrop.src = clean.src;
    curtain.src = fabric.src;
    ready = true;
    sync();
  }).catch(() => {
    // Never expose a half-assembled scene. Keep the original composite if
    // an asset is absent, corrupt, or unapproved by the gateway allowlist.
    ready = false;
    sync();
  });

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
