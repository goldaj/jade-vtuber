"use strict";
(() => {
  const scene = document.querySelector(".room-art");
  if (!scene || !CSS.supports("width", "1cqh")) return;
  const backdrop = scene.querySelector(".room-plane > img");
  const curtain = scene.querySelector(".room-curtain");
  const preference = matchMedia("(prefers-reduced-motion: reduce)");
  let ready = false, visible = false, frame = null, elapsed = 0, lastTime = null;

  async function loadLayer(path) {
    const image = new Image();
    image.src = path;
    await image.decode();
    if (!image.naturalWidth || !image.naturalHeight) throw new Error("art missing");
    return image;
  }

  // An independent, cleaned background and a transparent fabric master must
  // BOTH exist. Never warp a rectangular region of the composite background:
  // that region contains fixed wooden window-frame pixels.
  Promise.all([
    loadLayer("/assets/room-backdrop.webp"),
    loadLayer("/assets/room-curtain.webp")
  ]).then(([clean, fabric]) => {
    backdrop.src = clean.src;
    curtain.src = fabric.src;
    curtain.hidden = false;
    ready = true;
    sync();
  }).catch(() => {
    // Until the artist supplies the two real layers, keep the original static
    // illustration intact. A still window is better than a melting frame.
    curtain.hidden = true;
    ready = false;
    sync();
  });

  function paint(time) {
    if (lastTime === null) lastTime = time;
    elapsed += Math.min(50, time - lastTime);
    lastTime = time;
    const wave = Math.sin(elapsed / 950);
    curtain.style.transform = `translateX(${(wave * 1.5).toFixed(3)}%) rotate(${(wave * 1.2).toFixed(3)}deg)`;
    frame = requestAnimationFrame(paint);
  }

  function sync() {
    const moving = ready && visible && !document.hidden && !preference.matches;
    scene.toggleAttribute("data-paused", !moving);
    if (moving && frame === null) frame = requestAnimationFrame(paint);
    if (!moving) {
      if (frame !== null) cancelAnimationFrame(frame);
      frame = null;
      lastTime = null;
      curtain.style.transform = "";
    }
  }

  document.addEventListener("visibilitychange", sync);
  preference.addEventListener("change", sync);
  new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
    sync();
  }).observe(scene);
  sync();
})();
