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
  // Refuse a differently sized crop: even a tiny aspect ratio drift can
  // produce a noticeable seam as the scene scales.
  function valid(roomImage, bodyImage) {
    const ratio = roomImage.naturalWidth / roomImage.naturalHeight;
    return Math.abs(ratio - 941 / 1672) < .004 &&
      bodyImage.naturalWidth === 670 && bodyImage.naturalHeight === 940;
  }

  window.JadeSeatedScene = {
    get ready() { return ready; },
    assets: ASSETS
  };

  function activateWhenComplete() {
    if (!preparedImages || !window.JadeAvatar?.ready || !window.JadeAvatar?.canIsolateHead || ready) return;
    const [roomImage, bodyImage] = preparedImages;
    backdrop.src = roomImage.src;
    body.src = bodyImage.src;
    ready = true;
    room.dataset.seatedReady = "true";
    room.dispatchEvent?.(new Event("jade-seated-ready"));
    window.JadeAvatar.resize();
  }
  room.addEventListener?.("jade-avatar-ready", activateWhenComplete);
  Promise.all([preload(ASSETS.room), preload(ASSETS.body)])
    .then(([roomImage, bodyImage]) => {
      if (!valid(roomImage, bodyImage)) return;
      preparedImages = [roomImage, bodyImage];
      activateWhenComplete();
    })
    .catch(() => {
      // Production safety: retain old rendering and its own animations.
      room.dataset.seatedReady = "false";
    });
})();