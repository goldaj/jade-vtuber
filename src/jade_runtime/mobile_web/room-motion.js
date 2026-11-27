"use strict";
(() => {
  const room = document.querySelector(".room");
  const scene = document.querySelector(".room-art");
  const roomSelect = document.getElementById("room-selector");
  if (!room || !scene || !roomSelect) return;

  const kitchenImage = scene.querySelector(".room-plane > img");
  if (!kitchenImage) return;
  const kitchenSource = "/assets/room-kitchen-portrait.avif";
  let activeRoom = "bedroom";
  let selectionRevision = 0;
  let kitchenLoad = null;

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
    window.JadePreferences?.set("room", next);
    room.dataset.room = next;
    roomSelect.value = next;
    room.dispatchEvent(new Event("jade-room-changed"));
    const url = new URL(window.location.href);
    if (next === "bedroom") url.searchParams.delete("room");
    else url.searchParams.set("room", next);
    window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
  }

  roomSelect.addEventListener("change", () => { void changeRoom(roomSelect.value); });
  const fromUrl = new URLSearchParams(window.location.search).get("room");
  const explicitRoom = ["bedroom", "kitchen"].includes(fromUrl);
  const initialRoom = explicitRoom ? fromUrl : window.JadePreferences?.get("room", "bedroom");
  if (initialRoom === "kitchen") void changeRoom("kitchen");
  else if (explicitRoom) window.JadePreferences?.set("room", "bedroom");
})();
