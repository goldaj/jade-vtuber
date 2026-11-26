/* Session-only model catalogue and profile control. Fetching the catalogue
 * never loads a model; JadeAvatar owns every real selection and its result. */
"use strict";
(() => {
  const selector = document.getElementById("avatar-model-selector");
  const status = document.getElementById("avatar-model-status");
  const room = document.querySelector(".room");
  const fallback = Object.freeze([
    Object.freeze({id:"classic", label:"Modèle actuel", available:true,
      manifestUrl:"/model/Jade.model3.json", presentation:"seated", classicIntents:true, idleMotion:"Idle"}),
    Object.freeze({id:"next", label:"Nouveau modèle", available:false,
      manifestUrl:null, presentation:"full", classicIntents:false, idleMotion:null})
  ]);
  let profiles = fallback;
  let loaded = false;
  let selecting = false;
  const get = id => profiles.find(profile => profile.id === id) || null;

  function validate(data) {
    if (data?.version !== 1 || data.defaultId !== "classic" ||
        !Array.isArray(data.models) || data.models.length !== fallback.length) return null;
    const result = [];
    for (const expected of fallback) {
      const entries = data.models.filter(profile => profile?.id === expected.id);
      if (entries.length !== 1) return null;
      const profile = entries[0];
      const manifestUrl = expected.id === "classic"
        ? "/model/Jade.model3.json" : "/models/next/Jade.model3.json";
      if (typeof profile.label !== "string" || !profile.label.trim() || profile.label.length > 80 ||
          typeof profile.available !== "boolean" ||
          (expected.id === "classic" && !profile.available) ||
          profile.manifestUrl !== (profile.available ? manifestUrl : null) ||
          profile.presentation !== expected.presentation ||
          profile.classicIntents !== expected.classicIntents || profile.idleMotion !== expected.idleMotion) return null;
      // Keep only the supported fields. No arbitrary remote URL or model
      // capability can cross from a malformed catalogue into the renderer.
      result.push(Object.freeze({id:expected.id, label:profile.label.trim(), available:profile.available,
        manifestUrl:profile.manifestUrl, presentation:expected.presentation,
        classicIntents:expected.classicIntents, idleMotion:expected.idleMotion}));
    }
    return Object.freeze(result);
  }

  function renderOptions() {
    if (!selector) return;
    selector.replaceChildren(...profiles.map(profile => {
      const option = document.createElement("option");
      option.value = profile.id;
      option.textContent = profile.label + (profile.available ? "" : " — à venir");
      option.disabled = !profile.available;
      return option;
    }));
  }

  function syncState(failure = "") {
    if (!selector || !status) return;
    const avatar = window.JadeAvatar;
    const state = avatar?.state;
    const waiting = !loaded || !state || state.status === "idle" || state.status === "loading";
    selector.disabled = selecting || waiting || typeof avatar?.selectModel !== "function";
    // The selected option describes the model actually on screen, including
    // rollback after a failed switch, never the last requested filename.
    selector.value = get(state?.modelId)?.id || "classic";
    if (failure) status.textContent = failure;
    else if (state?.message) status.textContent = state.message;
    else if (waiting || selecting) status.textContent = "Chargement de Jade…";
    else if (state.status === "error") status.textContent = "Le modèle n’a pas pu être chargé. Tu peux réessayer.";
    else status.textContent = get("next").available
      ? "Choisis le modèle que tu souhaites afficher."
      : "Le nouveau modèle sera proposé ici quand il sera prêt.";
  }

  selector?.addEventListener("change", async () => {
    const avatar = window.JadeAvatar;
    const requested = selector.value;
    const profile = get(requested);
    if (selecting || !loaded || !avatar?.state ||
        ["idle", "loading"].includes(avatar.state.status) || typeof avatar.selectModel !== "function") {
      syncState();
      return;
    }
    if (!profile?.available) {
      syncState("Ce modèle n’est pas encore disponible.");
      return;
    }
    if (avatar.state.modelId === requested) {
      syncState();
      return;
    }
    selecting = true;
    const previousMessage = avatar.state.message;
    syncState();
    let failure = "";
    try {
      const selected = await avatar.selectModel(requested);
      if (!selected || avatar.state.modelId !== requested) failure = "Ce modèle n’a pas pu être chargé.";
    } catch (_) {
      failure = "Ce modèle n’a pas pu être chargé.";
    } finally {
      selecting = false;
      if (failure && avatar.state.message && avatar.state.message !== previousMessage) failure = "";
      syncState(failure);
    }
  });
  room?.addEventListener("jade-avatar-state", () => syncState());
  renderOptions();
  syncState();

  const ready = (async () => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 5000);
    try {
      const response = await fetch("/assets/avatar-models.json", {
        mode:"same-origin", credentials:"omit", cache:"no-store", signal:controller.signal
      });
      if (response.ok) profiles = validate(await response.json()) || fallback;
    } catch (_) {
      profiles = fallback;
    } finally {
      window.clearTimeout(timeout);
      loaded = true;
      renderOptions();
      syncState();
    }
    return profiles;
  })();
  window.JadeModelCatalog = Object.freeze({ready, get defaultId(){return "classic";},
    list:() => profiles, get});
})();
