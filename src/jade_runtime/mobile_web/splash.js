/* Dismiss the illustrated web splash as soon as the UI resources load.
 * Independent of app.js, so a conversation error cannot trap the user.
 * Android's earlier OS-controlled WebAPK launch icon is a separate screen.
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
  if (document.readyState === "complete") dismissSplash();
  else window.addEventListener("load", dismissSplash, {once:true});
})();
