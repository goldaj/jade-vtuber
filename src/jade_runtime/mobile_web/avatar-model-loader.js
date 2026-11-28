/* Own every resource of one Live2D load, including partially failed loads.
 * The caller must dispose the returned lease before loading another model. */
"use strict";
(() => {
  let occupied = false;
  let cleanupFailure = null;

  function localAsset(path, manifest) {
    if (typeof path !== "string" || !path) throw new Error("Invalid model asset");
    const url = new URL(path, manifest);
    const folder = new URL(".", manifest);
    if (url.origin !== folder.origin || !url.pathname.startsWith(folder.pathname) ||
        url.search || url.hash || url.username || url.password)
      throw new Error("Model asset outside its folder");
    return url.href;
  }

  function guardCoreConstruction(PIXI, settings) {
    const runtime = PIXI.live2d.Live2DFactory?.findRuntime?.(settings);
    if (!runtime?.createInternalModel) return () => {};
    const original = runtime.createInternalModel;
    // Adapter 0.4.0 otherwise loses a newly allocated Core if its internal
    // model constructor throws. The single-load lease bounds this guard.
    const guarded = function(core, ...args) {
      try { return original.call(this, core, ...args); }
      catch (error) {
        const moc = core.__moc;
        const errors = [];
        try { core.release?.(); } catch (failure) { errors.push(failure); }
        try { moc?.release?.(); } catch (failure) { errors.push(failure); }
        if (errors.length) {
          const failure = new Error("Failed model Core could not be released");
          failure.cleanupFailed = true;
          throw failure;
        }
        throw error;
      }
    };
    runtime.createInternalModel = guarded;
    return () => {
      if (runtime.createInternalModel === guarded) runtime.createInternalModel = original;
    };
  }

  async function readManifest(manifest, retry) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      let response;
      try {
        response = await fetch(manifest.href, {
          mode:"same-origin", credentials:"omit", cache:"no-store", signal:controller.signal
        });
      } catch (error) {
        if (!retry || (error.name !== "AbortError" && error.name !== "TypeError")) throw error;
      }
      if (response?.ok) return await response.json();
      if (!retry || (response && ![502, 503, 504].includes(response.status)))
        throw new Error("Model manifest unavailable");
    } finally { clearTimeout(timeout); }
    await new Promise(resolve => setTimeout(resolve, 250));
    return readManifest(manifest, false);
  }

  async function load(profile) {
    if (occupied) throw cleanupFailure || new Error("Dispose the previous model before loading another");
    const PIXI = window.PIXI;
    if (!PIXI?.live2d?.Live2DModel?.fromSync || !PIXI.Texture?.from)
      throw new Error("Live2D loader unavailable");
    occupied = true;
    let candidate = null, disposed = false;
    const textures = new Set();
    const dispose = () => {
      if (disposed) return;
      const errors = [];
      const attempt = action => { try { action(); } catch (error) { errors.push(error); } };
      if (candidate) {
        for (const texture of candidate.textures || []) textures.add(texture);
        attempt(() => { candidate.autoUpdate = false; });
        attempt(() => candidate.parent?.removeChild(candidate));
        if (candidate.internalModel) {
          // The lease releases textures separately, exactly once. The SDK
          // destroys motion/expression managers, Core, MOC and renderer here.
          attempt(() => candidate.destroy({children:true}));
        } else {
          // SDK destroy() assumes internalModel exists even after an early
          // failure. Still notify XHR listeners and destroy its container.
          attempt(() => candidate.emit?.("destroy"));
          attempt(() => candidate.unregisterInteraction?.());
          attempt(() => PIXI.Container.prototype.destroy.call(candidate, {children:true}));
        }
        candidate = null;
      }
      for (const texture of textures) {
        if (texture?.baseTexture) attempt(() => texture.destroy(true));
      }
      textures.clear();
      disposed = true;
      if (errors.length) {
        // Never permit a second allocation if release was not confirmed.
        const error = new Error("Model resources could not be released");
        error.cleanupFailed = true;
        cleanupFailure = error;
        throw error;
      }
      occupied = false;
    };
    try {
      const manifest = new URL(profile.manifestUrl, window.location.href);
      if (manifest.origin !== window.location.origin) throw new Error("Non-local model");
      const settings = await readManifest(manifest, profile.id === "next");
      const refs = settings?.FileReferences;
      if (settings?.Version !== 3 || !refs || !Array.isArray(refs.Textures) ||
          !refs.Textures.length || refs.Textures.length > 64)
        throw new Error("Invalid model manifest");
      localAsset(refs.Moc, manifest);
      for (const key of ["Physics", "Pose", "DisplayInfo", "UserData"])
        if (refs[key]) localAsset(refs[key], manifest);
      for (const expression of refs.Expressions || []) localAsset(expression.File, manifest);
      for (const motions of Object.values(refs.Motions || {})) {
        for (const motion of motions) {
          localAsset(motion.File, manifest);
          if (motion.Sound) localAsset(motion.Sound, manifest);
        }
      }
      settings.url = manifest.href;
      // Adapter setup starts textures in parallel with the MOC and can lose
      // their handles on failure. Own them first and drain every load before
      // proceeding; the adapter then reuses the valid entries in Pixi's cache.
      const pending = refs.Textures.map(path => {
        try {
          const texture = PIXI.Texture.from(localAsset(path, manifest), {
            resourceOptions:{autoLoad:false, crossorigin:"anonymous"}
          });
          textures.add(texture);
          return texture.baseTexture.valid ? Promise.resolve(texture)
            : Promise.resolve(texture.baseTexture.resource.load()).then(() => texture);
        } catch (error) { return Promise.reject(error); }
      });
      const loaded = await Promise.allSettled(pending);
      const failure = loaded.find(result => result.status === "rejected");
      if (failure) throw failure.reason;
      const restoreRuntime = guardCoreConstruction(PIXI, settings);
      try {
        await new Promise((resolve, reject) => {
          candidate = PIXI.live2d.Live2DModel.fromSync(settings, {
            autoUpdate:false, autoInteract:false, motionPreload:"NONE",
            onLoad:resolve, onError:reject
          });
        });
      } finally { restoreRuntime(); }
      return Object.freeze({model:candidate, dispose});
    } catch (error) {
      dispose();
      if (error?.cleanupFailed) {
        occupied = true;
        cleanupFailure = error;
      }
      throw error;
    }
  }
  window.JadeAvatarModelLoader = Object.freeze({load});
})();
