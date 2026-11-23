/* Reports an app initialization failure instead of a silent CSP form refusal. */
"use strict";
(() => {
  const form = document.getElementById("auth-form");
  const feedback = document.getElementById("auth-feedback");
  if (!form || !feedback) return;
  form.addEventListener("submit", event => {
    if (window.JadeAuthReady) return;
    event.preventDefault();
    feedback.textContent = "L'interface Jade n'a pas pu démarrer. Recharge cette page après avoir vérifié Jade sur le PC.";
  }, {capture:true});
})();
