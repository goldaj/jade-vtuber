/* Failed SDK setups must release the resources that the adapter can orphan. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname,
  "../src/jade_runtime/mobile_web/avatar-model-loader.js"), "utf8");
const profile = {manifestUrl:"/models/next/Jade.model3.json"};

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return {promise, resolve, reject};
}
async function flush() { for (let i = 0; i < 30; i++) await Promise.resolve(); }

function client({manifest, setup = "success", textureGates = {}, brokenCleanup = false} = {}) {
  const settings = manifest || {Version:3, FileReferences:{Moc:"Jade.moc3",Textures:["a.png","b.png"]}};
  const events = [], textures = new Map(), models = [];
  let calls = 0, coreReleases = 0, mocReleases = 0;
  const runtime = {createInternalModel() {
    if (setup === "constructor-error") throw new Error("internal constructor failed");
    return {destroy() { coreReleases++; mocReleases++; }};
  }};
  const originalConstructor = runtime.createInternalModel;
  class Container {
    destroy() { this.containerDestroyed = true; events.push("container-destroy"); }
  }
  const PIXI = {Container, Texture:{from(url, options) {
    assert.equal(options.resourceOptions.autoLoad,false);
    if (!textures.get(url)?.baseTexture) {
      const filename = new URL(url).pathname.split("/").at(-1);
      const gate = textureGates[filename];
      const baseTexture = {valid:false,resource:{load() {
        return (gate?.promise || Promise.resolve()).then(() => {baseTexture.valid = true;});
      }}};
      textures.set(url, {baseTexture, destroyed:0, destroy(withBase) {
        assert.equal(withBase,true); this.destroyed++;
        assert.equal(this.destroyed,1,"each owned texture is released exactly once");
        events.push(`texture-destroy:${filename}`); this.baseTexture = null;
      }});
      events.push(`texture-create:${filename}`);
    }
    return textures.get(url);
  }}, live2d:{Live2DFactory:{findRuntime:() => runtime}, Live2DModel:{fromSync(data, options) {
    calls++;
    assert.equal(data.url,"https://jade.example/models/next/Jade.model3.json");
    assert.equal(options.autoUpdate,false);
    assert.equal(options.autoInteract,false);
    assert.equal(options.motionPreload,"NONE");
    events.push("model-create");
    const model = {textures:[],autoUpdate:false,internalModel:null,
      emit(name) { events.push(`model-event:${name}`); },
      unregisterInteraction() { events.push("interaction-release"); },
      destroy(options) {
        assert(this.internalModel,"partial models require container cleanup instead of SDK destroy");
        assert.equal(options.children,true);
        assert(!options.texture,"texture ownership belongs to the lease");
        this.destroyed = true; events.push("model-destroy");
        if (brokenCleanup) throw new Error("release failed");
        this.internalModel.destroy();
      }};
    models.push(model);
    Promise.resolve().then(() => {
      if (setup === "partial-error") throw new Error("MOC failed before internal model");
      const core = {__moc:{release(){mocReleases++;}},release(){
        coreReleases++;
        if (brokenCleanup) throw new Error("core release failed");
      }};
      model.internalModel = runtime.createInternalModel(core);
      if (setup === "full-error") throw new Error("optional setup failed");
      model.textures = data.FileReferences.Textures.map(file => textures.get(new URL(file,data.url).href));
    }).then(options.onLoad,options.onError);
    return model;
  }}}};
  const window = {PIXI,location:{href:"https://jade.example/",origin:"https://jade.example"}};
  const context = {window,URL,AbortController,setTimeout,clearTimeout,
    fetch:async () => ({ok:true,json:async () => structuredClone(settings)})};
  vm.runInNewContext(source,context,{filename:"avatar-model-loader.js"});
  return {loader:window.JadeAvatarModelLoader,textures,models,events,runtime,originalConstructor,
    get calls(){return calls;},get coreReleases(){return coreReleases;},get mocReleases(){return mocReleases;}};
}

(async () => {
  const valid = client();
  const lease = await valid.loader.load(profile);
  assert.equal(valid.calls,1);
  assert.equal(valid.runtime.createInternalModel,valid.originalConstructor,"temporary SDK guard is restored");
  assert.equal(valid.textures.size,2);
  await assert.rejects(valid.loader.load(profile),/Dispose the previous/);
  lease.dispose(); lease.dispose();
  assert(lease.model.destroyed);
  assert.equal(valid.coreReleases,1); assert.equal(valid.mocReleases,1);
  assert([...valid.textures.values()].every(texture => texture.destroyed === 1));
  assert(valid.events.indexOf("model-destroy") < valid.events.indexOf("texture-destroy:a.png"));

  // Failure in one image cannot free the slot while another image is in flight.
  const first = deferred(), second = deferred();
  const failedTexture = client({textureGates:{"a.png":first,"b.png":second}});
  const pending = failedTexture.loader.load(profile);
  pending.catch(() => {});
  await flush(); first.reject(new Error("texture download failed")); await flush();
  assert.equal(failedTexture.calls,0);
  assert([...failedTexture.textures.values()].every(texture => texture.destroyed === 0));
  await assert.rejects(failedTexture.loader.load(profile),/Dispose the previous/);
  second.resolve(); await assert.rejects(pending,/texture download failed/);
  assert([...failedTexture.textures.values()].every(texture => texture.destroyed === 1));

  for (const setup of ["partial-error","full-error","constructor-error"]) {
    const broken = client({setup});
    await assert.rejects(broken.loader.load(profile));
    assert.equal(broken.calls,1);
    assert([...broken.textures.values()].every(texture => texture.destroyed === 1),setup);
    assert.equal(broken.runtime.createInternalModel,broken.originalConstructor);
    if (setup === "full-error") {
      assert(broken.models[0].destroyed); assert.equal(broken.coreReleases,1); assert.equal(broken.mocReleases,1);
    } else {
      assert(broken.models[0].containerDestroyed);
      assert(broken.events.includes("model-event:destroy"),"cancel SDK requests on a partial candidate");
      assert(broken.events.includes("interaction-release"));
      if (setup === "constructor-error") {
        assert.equal(broken.coreReleases,1); assert.equal(broken.mocReleases,1);
      }
    }
    // Ordinary load failure releases ownership, allowing a subsequent attempt.
    const before = broken.calls;
    await assert.rejects(broken.loader.load(profile));
    assert.equal(broken.calls,before+1);
  }

  for (const setup of ["success","constructor-error"]) {
    const blocked = client({setup,brokenCleanup:true});
    if (setup === "success") {
      const loaded = await blocked.loader.load(profile);
      assert.throws(() => loaded.dispose(), error => error.cleanupFailed === true);
    } else {
      await assert.rejects(blocked.loader.load(profile),error => error.cleanupFailed === true);
      assert.equal(blocked.mocReleases,1,"attempt MOC release even when Core release fails");
    }
    await assert.rejects(blocked.loader.load(profile),error => error.cleanupFailed === true);
    assert.equal(blocked.calls,1,"unconfirmed release must block every new allocation");
  }

  const duplicate = client({manifest:{Version:3,FileReferences:{Moc:"Jade.moc3",Textures:["a.png","a.png"]}}});
  (await duplicate.loader.load(profile)).dispose();
  assert.equal(duplicate.textures.size,1);
  assert.equal([...duplicate.textures.values()][0].destroyed,1);

  for (const manifest of [
    {Version:2,FileReferences:{Moc:"Jade.moc3",Textures:["a.png"]}},
    {Version:3,FileReferences:{Moc:"../classic.moc3",Textures:["a.png"]}},
    {Version:3,FileReferences:{Moc:"Jade.moc3",Textures:[]}},
    {Version:3,FileReferences:{Moc:"Jade.moc3",Textures:["https://other.example/a.png"]}},
    {Version:3,FileReferences:{Moc:"Jade.moc3",Textures:["a.png"],Motions:{Idle:[{File:"../idle.motion3.json"}]}}}
  ]) {
    const invalid = client({manifest});
    await assert.rejects(invalid.loader.load(profile));
    assert.equal(invalid.calls,0,"invalid manifests never reach the SDK");
    assert.equal(invalid.textures.size,0);
  }
  console.log("Mobile avatar resource loader tests passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
