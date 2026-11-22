/* The deferred script runs after HTML parsing and stylesheets are ready.
 * Never wait for window.load: slow/unavailable Live2D and images must not
 * leave the illustrated launch layer in front of the token form or app.
 * Independent of app.js and of Android's earlier native launch screen.
 */
"use strict";
(() => {
  const splash = document.getElementById("jade-launch-splash");
  if (!splash) return;
  let dismissed = false;
  function dismissSplash() {
    if (dismissed) return;
    dismissed = true;
    requestAnimationFrame(() => {
      splash.setAttribute("aria-hidden", "true");
      splash.classList.add("is-dismissed");
      splash.addEventListener("transitionend", () => splash.remove(), {once:true});
      window.setTimeout(() => splash.remove(), 420);
    });
  }
  // The script tag is defer, so the modal and page DOM already exist here.
  dismissSplash();
})();
