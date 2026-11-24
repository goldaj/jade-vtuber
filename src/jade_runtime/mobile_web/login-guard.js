/* Only the token form starts before authentication; no tokens are persisted. */
"use strict";
(() => {
  const form = document.getElementById("auth-form");
  const input = document.getElementById("auth-token");
  const feedback = document.getElementById("auth-feedback");
  const submit = form?.querySelector('button[type="submit"]');
  const modal = document.getElementById("auth-modal");
  if (!form || !input || !feedback || !submit || !modal) return;
  let pending = false;
  let coreReady = false;
  let coreLoad = null;
  let optionalStarted = false;

  function loadStyle(url) {
    return new Promise((resolve, reject) => {
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = url;
      link.onload = resolve;
      link.onerror = () => reject(new Error("Feuille de style indisponible."));
      document.head.appendChild(link);
    });
  }

  function loadScript(url) {
    return new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = url;
      script.async = false;
      script.onload = resolve;
      script.onerror = () => reject(new Error("Module du salon indisponible."));
      document.head.appendChild(script);
    });
  }

  async function loadCore(value) {
    if (coreReady) return;
    if (!coreLoad) {
      coreLoad = (async () => {
        if (!document.querySelector(".shell")) {
          // The salon document is neither requested nor parsed pre-login.
          const response = await fetch("/assets/salon.html", {
            method:"GET",mode:"same-origin",credentials:"omit",cache:"no-store",
            headers:{"Authorization":"Bearer " + value}
          });
          if (response.status === 401) throw new Error("Jeton refusé par le salon.");
          if (!response.ok) throw new Error("Salon indisponible (HTTP " + response.status + ").");
          const fragment = document.createElement("template");
          fragment.innerHTML = await response.text();
          if (!fragment.content.querySelector(".shell")) throw new Error("Structure du salon invalide.");
          document.body.insertBefore(fragment.content, modal);
        }
        await Promise.all([loadStyle("/assets/styles.css"), loadStyle("/assets/jade-theme.css")]);
        await loadScript("/assets/app.js");
        if (!window.JadeMobileApp?.login) throw new Error("Le salon n'a pas pu démarrer.");
        coreReady = true;
      })().catch(error => { coreLoad = null; throw error; });
    }
    await coreLoad;
  }

  function loadOptionalAfterLogin() {
    if (optionalStarted) return;
    optionalStarted = true;
    // Optional assets must never postpone the chat or the private login.
    void (async () => {
      for (const url of [
        "/assets/duplex-client.js",
        "/assets/room-motion.js",
        "/assets/seated-scene.js",
        "/assets/portrait-bedroom-motion.js",
        "/assets/head-isolation.js",
        "/vendor/pixi.min.js",
        "/vendor/pixi-unsafe-eval.min.js",
        "/vendor/live2dcubismcore.min.js",
        "/vendor/cubism4.min.js",
        "/assets/avatar.js",
      ]) {
        try { await loadScript(url); }
        catch (error) {
          /* Chat remains usable without the visual/voice enhancement. */
          if(url==="/assets/portrait-bedroom-motion.js"){
            const status=document.getElementById("portrait-motion-status");
            if(status)status.textContent="Module des animations indisponible.";
            console.warn("Portrait bedroom animation module unavailable:",error);
          }
        }
      }
    })();
  }

  window.JadeLogin = {show() {
    modal.classList.remove("hidden");
    feedback.textContent = "";
    input.focus();
  }};

  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (pending) return;
    const value = input.value;
    if (value.length < 32 || value.length > 256) {
      feedback.textContent = "Le jeton doit contenir entre 32 et 256 caractères.";
      input.focus();
      return;
    }
    pending = true;
    submit.disabled = true;
    feedback.textContent = "Vérification du jeton auprès de Jade…";
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch("/api/auth", {
        method:"POST",mode:"same-origin",credentials:"omit",cache:"no-store",
        headers:{"Authorization":"Bearer " + value, "Content-Type":"application/json"},
        body:"{}",signal:controller.signal
      });
      if (response.status === 401) throw new Error("Jeton refusé. Vérifie celui configuré sur le PC.");
      if (response.status === 403) throw new Error("Accès privé refusé. Vérifie Tailscale et le compte autorisé.");
      if (!response.ok) throw new Error("Connexion refusée par Jade (HTTP " + response.status + ").");
      if ((await response.json()).status !== "ok") throw new Error("Réponse de connexion inattendue.");
      feedback.textContent = "Connexion vérifiée. Ouverture du salon…";
      await loadCore(value);
      window.JadeMobileApp.login(value);
      loadOptionalAfterLogin();
    } catch (error) {
      feedback.textContent = error.name === "AbortError"
        ? "Délai dépassé. Vérifie Jade sur le PC et Tailscale."
        : error instanceof TypeError
          ? "Serveur Jade inaccessible. Vérifie la connexion et Tailscale."
          : (error.message || "Connexion impossible.");
    } finally {
      window.clearTimeout(timeout);
      pending = false;
      submit.disabled = false;
    }
  });
})();
