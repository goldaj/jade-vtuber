"use strict";
(() => {
  const scene = document.querySelector(".room-art");
  if (!CSS.supports("width", "1cqh")) return;

  const art = scene.querySelector("img");
  const curtain = scene.querySelector("canvas");
  const context = curtain.getContext("2d");
  const preference = matchMedia("(prefers-reduced-motion: reduce)");
  const patch = { x: 906, y: 46, w: curtain.width, h: curtain.height };
  let visible = false;
  let ready = false;
  let frame = null;
  let lastTime = null;
  let elapsed = 0;

  function paint(seconds) {
    const phase = seconds * (2 * Math.PI / 7.2);
    // Stretch two pieces of each band around the fold, keeping the edges
    // aligned with the underlying static illustration.
    for (let row = 0; row < patch.h; row += 5) {
      const band = Math.min(5, patch.h - row);
      const depth = row / patch.h;
      const fold = Math.round(161 - 49 * depth);
      const envelope = Math.sin(Math.PI * depth) * depth;
      const shifted = fold + 14 * envelope * Math.sin(phase - depth * 2.4);
      context.drawImage(art, patch.x, patch.y + row, fold, band,
        0, row, shifted, band);
      context.drawImage(art, patch.x + fold, patch.y + row, patch.w - fold, band,
        shifted, row, patch.w - shifted, band);
    }
  }

  function step(time) {
    if (lastTime === null) lastTime = time;
    if (time - lastTime >= 40) {
      elapsed += time - lastTime;
      lastTime = time;
      paint(elapsed / 1000);
    }
    frame = requestAnimationFrame(step);
  }

  function sync() {
    const moving = ready && visible && !document.hidden && !preference.matches;
    scene.toggleAttribute("data-paused", !moving);
    if (moving && context && frame === null) frame = requestAnimationFrame(step);
    if (!moving && frame !== null) {
      cancelAnimationFrame(frame);
      frame = null;
      lastTime = null;
    }
  }

  document.addEventListener("visibilitychange", sync);
  preference.addEventListener("change", sync);
  new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
    sync();
  }).observe(scene);
  art.decode().then(() => {
    ready = true;
    sync();
  }).catch(() => {});
})();
