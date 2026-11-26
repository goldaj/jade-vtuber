/* The portrait room outlives avatar changes. Only the classic avatar owns the
 * seated body, and its pending image must never survive a model selection. */
"use strict";
(() => {
  const room = document.querySelector(".room");
  const body = document.getElementById("portrait-seated-body");
  if (!room || !body) return;

  const ASSETS = Object.freeze({body:"/assets/jade-seated-body.avif"});
  const BASE_LAYOUT = Object.freeze({top:.406699, height:.562201});
  let layout = BASE_LAYOUT;
  let ready = false;
  let generation = 0;
  let bodyLoad = null;

  function preload(url) {
    const image = new Image();
    let settled = false, rejectLoad;
    const promise = new Promise((resolve, reject) => {
      rejectLoad = reject;
      image.onload = () => {
        if (settled) return;
        settled = true;
        image.onload = image.onerror = null;
        if (!image.naturalWidth || !image.naturalHeight) reject(new Error("empty picture"));
        else resolve(image);
      };
      image.onerror = () => {
        if (settled) return;
        settled = true;
        image.onload = image.onerror = null;
        reject(new Error("picture unavailable"));
      };
      image.src = url;
    });
    return {promise, cancel() {
      if (settled) return;
      settled = true;
      image.onload = image.onerror = null;
      image.removeAttribute("src");
      rejectLoad(new Error("picture cancelled"));
    }};
  }

  function deactivate() {
    generation++;
    ready = false;
    room.dataset.seatedReady = "false";
    room.dataset.seatedCompositor = "false";
    body.removeAttribute("src");
    body.style.removeProperty("--seated-body-top");
    body.style.removeProperty("--seated-body-height");
    layout = BASE_LAYOUT;
    bodyLoad?.cancel();
    bodyLoad = null;
    room.dispatchEvent?.(new Event("jade-seated-ready"));
  }

  window.JadeSeatedScene = {
    get ready() { return ready; },
    get layout() { return layout; },
    assets:ASSETS,
    deactivate
  };

  async function prepareSeated(avatar) {
    const revision = generation;
    const pending = preload(ASSETS.body);
    bodyLoad = pending;
    try {
      const bodyImage = await pending.promise;
      if (revision !== generation || !avatar.ready || !avatar.usesSeatedBody || !avatar.canIsolateHead) return;
      // Preserve the original 941x1672 registration. The revised crop only
      // extends the neck by 16 pixels; unrelated body crops stay rejected.
      if (bodyImage.naturalWidth !== 670 || ![940, 956].includes(bodyImage.naturalHeight))
        throw new Error("unsupported seated body crop");
      const extra = BASE_LAYOUT.height * (bodyImage.naturalHeight - 940) / 940;
      layout = Object.freeze({top:BASE_LAYOUT.top - extra, height:BASE_LAYOUT.height + extra});
      let layered = false;
      try {
        if (avatar.canComposeSeated)
          layered = Boolean(avatar.prepareSeatedComposition(bodyImage));
      } catch (error) {
        console.warn("Jade seated depth compositor unavailable:", error);
      }
      if (revision !== generation || !avatar.ready || !avatar.usesSeatedBody) return;
      body.style.setProperty("--seated-body-top", `${layout.top * 100}%`);
      body.style.setProperty("--seated-body-height", `${layout.height * 100}%`);
      body.src = bodyImage.src;
      ready = true;
      room.dataset.seatedReady = "true";
      room.dataset.seatedCompositor = layered ? "true" : "false";
      room.dispatchEvent?.(new Event("jade-seated-ready"));
      avatar.resize();
    } catch (_) {
      pending.cancel();
      if (revision === generation) {
        ready = false;
        room.dataset.seatedReady = "false";
        room.dataset.seatedCompositor = "false";
      }
    } finally {
      if (bodyLoad === pending) bodyLoad = null;
    }
  }

  function activateForAvatar() {
    const avatar = window.JadeAvatar;
    if (!avatar?.ready) return;
    if (avatar.usesSeatedBody) {
      if (ready || bodyLoad || !avatar.canIsolateHead) return;
      void prepareSeated(avatar);
      return;
    }
    deactivate();
  }
  room.addEventListener?.("jade-avatar-ready", activateForAvatar);
  activateForAvatar();
})();
