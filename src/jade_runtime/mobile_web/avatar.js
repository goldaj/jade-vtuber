/* Live2D Web adapter. Requires locally installed, licensed Cubism Web Core
 * plus PIXI 6.x and pixi-live2d-display Cubism 4 bundle.
 * None of those SDK binaries are redistributed by this repository.
 */
"use strict";
(() => {
  const target = document.getElementById("avatar-container");
  const fallback = document.getElementById("avatar-fallback");
  const status = document.getElementById("avatar-state");
  let model = null;
  let pixi = null;
  let mouth = 0;
  let lastExpression = "neutral";
  let observer = null;

  const avatar = {
    get ready() { return Boolean(model); },
    setMouth(value) {
      mouth = Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : 0;
    },
    setIntent(intent) {
      lastExpression = intent;
      if (!model || typeof model.expression !== "function") return;
      const expressions = {
        playful: "WinkR", excited: "Smile", curious: "Surprised",
        tender: "Smile", reassuring: "Smile", serious: "Sad"
      };
      try {
        // A missing expression must not interrupt the conversation.
        if (expressions[intent]) {
          const action = model.expression(expressions[intent]);
          if (action && typeof action.catch === "function") action.catch(() => {});
        }
      } catch (_) {}
    },
  };
  window.JadeAvatar = avatar;

  function resize() {
    if (!pixi || !model) return;
    const width = Math.max(1, target.clientWidth);
    const height = Math.max(1, target.clientHeight);
    pixi.renderer.resize(width, height);
    const naturalWidth = Math.max(model.width / (model.scale.x || 1), 1);
    const naturalHeight = Math.max(model.height / (model.scale.y || 1), 1);
    const scale = Math.min((width * .95) / naturalWidth, (height * 1.32) / naturalHeight);
    model.scale.set(Math.max(.05, scale));
    model.position.set(width / 2, height * .63);
  }

  async function load() {
    const PIXI = window.PIXI;
    if (!PIXI || !PIXI.live2d || !PIXI.live2d.Live2DModel ||
        !window.Live2DCubismCore) {
      status.textContent = "Le décor est prêt. Le moteur Live2D doit encore être installé sur le PC (voir documentation).";
      return;
    }
    try {
      pixi = new PIXI.Application({
        resizeTo: target, autoDensity: true,
        resolution: Math.min(window.devicePixelRatio || 1, 2),
        antialias: true, backgroundAlpha: 0, transparent: true
      });
      target.appendChild(pixi.view);
      model = await PIXI.live2d.Live2DModel.from("/model/Jade.model3.json", {
        autoInteract: false
      });
      model.anchor.set(.5, .5);
      pixi.stage.addChild(model);
      resize();
      observer = new ResizeObserver(resize);
      observer.observe(target);
      fallback.classList.add("hidden");
      // No green screen/chroma key. WebGL keeps the model alpha transparent
      // and the CSS room is the actual background.
      pixi.ticker.add(() => {
        try {
          const core = model?.internalModel?.coreModel;
          if (core && typeof core.setParameterValueById === "function") {
            core.setParameterValueById("ParamMouthOpenY", mouth);
          }
        } catch (_) {}
      }, undefined, PIXI.UPDATE_PRIORITY?.LOW ?? -50);
      avatar.setIntent(lastExpression);
      if (typeof model.motion === "function") {
        try {
          const animation = model.motion("Idle", 0);
          if (animation && animation.catch) animation.catch(() => {});
        } catch (_) {}
      }
    } catch (_) {
      if (observer) observer.disconnect();
      if (pixi) { try { pixi.destroy(true, {children: true}); } catch (_) {} }
      pixi = null;
      model = null;
      status.textContent = "Impossible de charger le modèle r20 : vérifier Git LFS, WebGL et les composants Cubism.";
      fallback.classList.remove("hidden");
    }
  }
  load();
})();
