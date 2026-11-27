"use strict";
(() => {
  const room = document.querySelector(".room");
  const scene = document.querySelector(".room-art");
  const roomSelect = document.getElementById("room-selector");
  if (!room || !scene || !roomSelect) return;

  const staticImage = scene.querySelector(".room-plane > img");
  if (!staticImage) return;
  const staticSources = Object.freeze({
    kitchen: "/assets/room-kitchen-portrait.avif",
    living: "/assets/room-living-portrait.avif"
  });
  const rooms = ["bedroom", ...Object.keys(staticSources)];
  const loads = new Map();
  let activeRoom = "bedroom";
  let selectionRevision = 0;

  function loadStaticRoom(next) {
    if (!loads.has(next)) {
      const image = new Image();
      image.src = staticSources[next];
      const pending = image.decode().then(() => {
        if (!image.naturalWidth || !image.naturalHeight) throw new Error("room unavailable");
        return image.src;
      }).catch(error => {
        loads.delete(next);
        throw error;
      });
      loads.set(next, pending);
    }
    return loads.get(next);
  }

  async function changeRoom(next) {
    if (!rooms.includes(next)) return;
    const revision = ++selectionRevision;
    let source = null;
    try {
      if (next !== "bedroom") source = await loadStaticRoom(next);
    } catch (_) {
      if (revision === selectionRevision) roomSelect.value = activeRoom;
      return;
    }
    // A previous decode must never replace a more recently selected room.
    if (revision !== selectionRevision) return;
    if (source !== null) staticImage.src = source;
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
  const explicitRoom = rooms.includes(fromUrl);
  const initialRoom = explicitRoom ? fromUrl : window.JadePreferences?.get("room", "bedroom");
  if (rooms.includes(initialRoom) && initialRoom !== "bedroom") void changeRoom(initialRoom);
  else if (explicitRoom) window.JadePreferences?.set("room", "bedroom");
})();
