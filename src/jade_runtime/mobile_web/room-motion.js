"use strict";
(() => {
  const room = document.querySelector(".room");
  const scene = document.querySelector(".room-art");
  const roomSelect = document.getElementById("room-selector");
  if (!room || !scene || !roomSelect) return;

  const kitchenImage = scene.querySelector(".room-plane > img");
  const kitchenEffects = scene.querySelector(".kitchen-effects");
  if (!kitchenImage || !kitchenEffects) return;
  const kitchenSource = "/assets/room-kitchen.webp";
  const supportsKitchenEffects = typeof CSS !== "undefined" && CSS.supports("width", "1cqh");
  const preference = matchMedia("(prefers-reduced-motion: reduce)");
  let activeRoom = "bedroom";
  let selectionRevision = 0;
  let visible = true;
  let kitchenLoad = null;

  function sync() {
    const enabled = activeRoom === "kitchen" && supportsKitchenEffects && !preference.matches;
    kitchenEffects.hidden = !enabled;
    scene.toggleAttribute("data-paused", !(enabled && visible && !document.hidden));
  }

  function loadKitchen() {
    if (!kitchenLoad) {
      const image = new Image();
      image.src = kitchenSource;
      kitchenLoad = image.decode().then(() => {
        if (!image.naturalWidth || !image.naturalHeight) throw new Error("kitchen unavailable");
        kitchenImage.src = image.src;
      }).catch(error => {
        kitchenLoad = null;
        throw error;
      });
    }
    return kitchenLoad;
  }

  async function changeRoom(next) {
    if (next !== "bedroom" && next !== "kitchen") return;
    const revision = ++selectionRevision;
    try {
      if (next === "kitchen") await loadKitchen();
    } catch (_) {
      if (revision === selectionRevision) roomSelect.value = activeRoom;
      return;
    }
    if (revision !== selectionRevision) return;
    activeRoom = next;
    room.dataset.room = next;
    roomSelect.value = next;
    sync();
    room.dispatchEvent(new Event("jade-room-changed"));
    const url = new URL(window.location.href);
    if (next === "bedroom") url.searchParams.delete("room");
    else url.searchParams.set("room", next);
    window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
  }

  roomSelect.addEventListener("change", () => { void changeRoom(roomSelect.value); });
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
  if (new URLSearchParams(window.location.search).get("room") === "kitchen") void changeRoom("kitchen");
})();
