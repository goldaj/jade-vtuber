/* Hybrid bedroom: one responsive scene coordinate system for static seated body
 * and animated r20 head. Assets load only after successful authentication.
 * A missing/invalid pair must leave the old bedroom and kitchen untouched. */
"use strict";
(() => {
  const room = document.querySelector(".room");
  const backdrop = document.getElementById("portrait-bedroom");
  const body = document.getElementById("portrait-seated-body");
  if (!room || !backdrop || !body) return;

  const ASSETS = Object.freeze({
    room: "/assets/room-bedroom-portrait.avif",
    body: "/assets/jade-seated-body.avif"
  });
  const BASE_LAYOUT = Object.freeze({top: .406699, height: .562201});
  let layout = BASE_LAYOUT;
  let ready = false;
  let preparedImages = null;

  function preload(url) {
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => {
        if (!image.naturalWidth || !image.naturalHeight) reject(new Error("empty picture"));
        else resolve(image);
      };
      image.onerror = () => reject(new Error("picture unavailable"));
      image.src = url;
    });
  }

  // The body reference was extracted from a 941x1672 composition.
  // Accept the original crop and the revised crop with 16 extra pixels
  // above the neck. Reject unrelated crops to avoid a visible seam.
  function valid(roomImage, bodyImage) {
    const ratio = roomImage.naturalWidth / roomImage.naturalHeight;
    return Math.abs(ratio - 941 / 1672) < .004 &&
      bodyImage.naturalWidth === 670 && [940, 956].includes(bodyImage.naturalHeight);
  }

  window.JadeSeatedScene = {
    get ready() { return ready; },
    get layout() { return layout; },
    assets: ASSETS
  };

  function activateWhenComplete() {
    if (!preparedImages || !window.JadeAvatar?.ready || !window.JadeAvatar?.canIsolateHead || ready) return;
    const [roomImage, bodyImage] = preparedImages;
    // Preserve the original pixel scale and bottom anchor. Only the neck
    // extension occupies the new area above the original crop.
    const extra = BASE_LAYOUT.height * (bodyImage.naturalHeight - 940) / 940;
    layout = Object.freeze({top: BASE_LAYOUT.top - extra, height: BASE_LAYOUT.height + extra});
    body.style.setProperty("--seated-body-top", `${layout.top * 100}%`);
    body.style.setProperty("--seated-body-height", `${layout.height * 100}%`);
    // A depth compositor failure must NEVER replace seated Jade with a standing model.
    let layered = false;
    try {
      if (window.JadeAvatar.canComposeSeated)
        layered = Boolean(window.JadeAvatar.prepareSeatedComposition(bodyImage));
    } catch (error) {
      console.warn("Jade seated depth compositor unavailable:", error);
    }
    backdrop.src = roomImage.src;
    body.src = bodyImage.src;
    ready = true;
    room.dataset.seatedReady = "true";
    room.dataset.seatedCompositor = layered ? "true" : "false";
    room.dispatchEvent?.(new Event("jade-seated-ready"));
    window.JadeAvatar.resize();
  }
  room.addEventListener?.("jade-avatar-ready", activateWhenComplete);
  Promise.all([preload(ASSETS.room), preload(ASSETS.body)])
    .then(([roomImage, bodyImage]) => {
      if (!valid(roomImage, bodyImage)) {
        room.dataset.seatedReady = "false";
        console.warn("Unsupported seated Jade crop:", bodyImage.naturalWidth, bodyImage.naturalHeight);
        return;
      }
      preparedImages = [roomImage, bodyImage];
      activateWhenComplete();
    })
    .catch(() => {
      // Production safety: retain old rendering and its own animations.
      room.dataset.seatedReady = "false";
    });
})();