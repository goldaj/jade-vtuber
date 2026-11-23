/* The login form must never silently submit while the app script is loading.
 * Queue an explicit tap and replay it once the lightweight app is initialized.
 */
"use strict";
(() => {
  const form = document.getElementById("auth-form");
  const feedback = document.getElementById("auth-feedback");
  if (!form || !feedback) return;
  let pendingSubmit = false;
  let pendingWarning = null;
  form.addEventListener("submit", event => {
    if (window.JadeAuthReady) return;
    event.preventDefault();
    pendingSubmit = true;
    feedback.textContent = "Chargement du salon… Connexion automatique dès que l'application est prête.";
    if (pendingWarning !== null) return;
    pendingWarning = window.setTimeout(() => {
      pendingWarning = null;
      if (!pendingSubmit || window.JadeAuthReady) return;
      feedback.textContent = "Le salon met trop de temps à démarrer. Vérifie Jade sur le PC puis recharge l'application.";
    }, 15000);
  }, {capture:true});
  window.JadeAuthResume = () => {
    if (!pendingSubmit || !window.JadeAuthReady) return;
    pendingSubmit = false;
    if (pendingWarning !== null) window.clearTimeout(pendingWarning);
    pendingWarning = null;
    form.requestSubmit();
  };
})();
