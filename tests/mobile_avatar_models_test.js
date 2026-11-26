/* Catalogue validation and the profile selector without a renderer or network. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const web = path.join(__dirname, "../src/jade_runtime/mobile_web");
const source = fs.readFileSync(path.join(web, "avatar-models.js"), "utf8");

function catalogue(nextAvailable = false) {
  return {version:1, defaultId:nextAvailable ? "next" : "classic", models:[
    {id:"classic", label:"Jade classique (r20)", available:true, manifestUrl:"/model/Jade.model3.json",
      presentation:"seated", classicIntents:true, idleMotion:"Idle"},
    {id:"next", label:"Jade actuelle (r21)", available:nextAvailable,
      manifestUrl:nextAvailable ? "/models/next/Jade.model3.json" : null,
      presentation:"full", classicIntents:false, idleMotion:nextAvailable ? "Idle" : null}
  ]};
}

class Element {
  constructor() { this.listeners = {}; this.children = []; this.disabled = true; this.value = ""; this.textContent = ""; }
  addEventListener(name, listener) { (this.listeners[name] ||= []).push(listener); }
  replaceChildren(...children) { this.children = children; }
  async emit(name) { for (const listener of this.listeners[name] || []) await listener({type:name, target:this}); }
}

function client({data = catalogue(), transport = "ok", withUi = true} = {}) {
  const selector = new Element(), status = new Element(), room = new Element();
  const document = {
    getElementById(id) { return withUi ? {"avatar-model-selector":selector, "avatar-model-status":status}[id] : null; },
    querySelector() { return room; }, createElement() { return new Element(); }
  };
  const timers = new Map(), requests = [], selections = [], lifecycle = [];
  let nextTimer = 0, resolveFetch;
  const window = {
    JadeConversation:{stopForModelChange() {
      lifecycle.push("stop");
      return () => lifecycle.push("resume");
    }},
    setTimeout(callback) { const id = ++nextTimer; timers.set(id, callback); return id; },
    clearTimeout(id) { timers.delete(id); }
  };
  const fetch = async (url, options) => {
    requests.push({url, options});
    if (transport === "reject") throw new Error("offline");
    if (transport === "pending" || transport === "timeout") {
      await new Promise((resolve, reject) => {
        resolveFetch = resolve;
        options.signal.addEventListener("abort", () => reject(new Error("aborted")), {once:true});
      });
    }
    return {ok:transport !== "http-error", async json(){
      if (transport === "invalid-json") throw new SyntaxError("invalid JSON");
      return data;
    }};
  };
  vm.runInNewContext(source, {window, document, fetch, AbortController, console}, {filename:"avatar-models.js"});
  function renderer(state = {status:"ready", modelId:"classic", requestedId:"classic", message:""}, select) {
    let currentState = state;
    const avatar = {get state(){return currentState;}, async selectModel(id){
      selections.push(id);
      lifecycle.push("select");
      return select ? select(id, update) : false;
    }};
    function update(next) { currentState = next; return room.emit("jade-avatar-state"); }
    window.JadeAvatar = avatar;
    return {avatar, update};
  }
  return {window, selector, status, room, timers, requests, selections, lifecycle, renderer,
    ready:window.JadeModelCatalog.ready,
    completeFetch(){resolveFetch();},
    async change(id){selector.value = id; await selector.emit("change");}
  };
}

(async () => {
  const waiting = client({transport:"pending"});
  assert.equal(waiting.selector.disabled, true, "selector waits for catalogue and renderer");
  assert.equal(waiting.selector.children[1].disabled, true, "future model is disabled even during catalogue loading");
  assert.equal(waiting.selections.length, 0);
  const existing = waiting.renderer(); await waiting.room.emit("jade-avatar-state");
  assert.equal(waiting.selector.disabled, true, "renderer readiness alone cannot unlock an unknown catalogue");
  waiting.completeFetch(); await waiting.ready;
  assert.equal(waiting.selector.disabled, false);
  assert.equal(waiting.selector.value, "classic");
  assert.equal(waiting.selector.children[1].textContent, "Jade actuelle (r21) — indisponible");
  assert.match(waiting.status.textContent, /classique est utilisé/);
  await waiting.change("next");
  assert.equal(waiting.selections.length, 0, "unavailable model never reaches the renderer");
  assert.equal(waiting.selector.value, "classic");
  assert.match(waiting.status.textContent, /pas encore disponible/);
  await waiting.change("untrusted");
  assert.equal(waiting.selections.length, 0, "unknown model never reaches the renderer");
  await waiting.change("classic");
  assert.equal(waiting.selections.length, 0, "selecting the already displayed model does not reload it");
  await existing.update({status:"loading", modelId:"classic", requestedId:"classic", message:"Chargement…"});
  assert.equal(waiting.selector.disabled, true);
  assert.equal(waiting.status.textContent, "Chargement…");
  await waiting.change("classic");
  assert.equal(waiting.selections.length, 0, "a forced change during loading is ignored");

  const available = client({data:catalogue(true)}); await available.ready;
  assert.equal(available.window.JadeModelCatalog.defaultId, "next");
  assert.equal(available.selector.disabled, true, "an available catalogue does not create a renderer");
  let finishSelection;
  available.renderer(undefined, async (id, update) => {
    await update({status:"loading", modelId:"classic", requestedId:id, message:"Chargement du nouveau modèle…"});
    await new Promise(resolve => { finishSelection = resolve; });
    await update({status:"ready", modelId:id, requestedId:id, message:"Nouveau modèle affiché."});
    return true;
  });
  await available.room.emit("jade-avatar-state");
  assert.equal(available.selector.children[1].disabled, false);
  assert.equal(available.selections.length, 0, "discovering an available model never selects it automatically");
  const change = available.change("next");
  await Promise.resolve(); await Promise.resolve();
  assert.equal(available.selector.disabled, true);
  assert.equal(available.selector.value, "classic", "the selector keeps the model actually displayed during loading");
  await available.change("next");
  assert.deepEqual(available.selections, ["next"], "a pending selection cannot trigger another load");
  assert.deepEqual(available.lifecycle, ["stop", "select"]);
  finishSelection(); await change;
  assert.equal(available.selector.disabled, false);
  assert.equal(available.selector.value, "next");
  assert.equal(available.status.textContent, "Nouveau modèle affiché.");
  assert.deepEqual(available.lifecycle, ["stop", "select", "resume"]);

  const rollback = client({data:catalogue(true)}); await rollback.ready;
  rollback.renderer(undefined, async (id, update) => {
    await update({status:"loading", modelId:"classic", requestedId:id, message:"Chargement…"});
    await update({status:"error", modelId:"classic", requestedId:id, message:"Chargement impossible. Le modèle actuel reste affiché."});
    return false;
  });
  await rollback.room.emit("jade-avatar-state"); await rollback.change("next");
  assert.equal(rollback.selector.value, "classic", "failed selection reflects the rolled back model");
  assert.equal(rollback.selector.disabled, false, "failure leaves the control available for another attempt");
  assert.equal(rollback.status.textContent, "Chargement impossible. Le modèle actuel reste affiché.");
  assert.deepEqual(rollback.lifecycle, ["stop", "select", "resume"]);

  const thrown = client({data:catalogue(true)}); await thrown.ready;
  thrown.renderer({status:"ready", modelId:"classic", requestedId:"classic", message:"Modèle actuel affiché."},
    async () => { throw new Error("unexpected renderer failure"); });
  await thrown.room.emit("jade-avatar-state"); await thrown.change("next");
  assert.equal(thrown.selector.value, "classic");
  assert.match(thrown.status.textContent, /n’a pas pu être chargé/,
    "unexpected errors cannot retain an old success message");

  const dishonest = client({data:catalogue(true)}); await dishonest.ready;
  dishonest.renderer(undefined, async () => true);
  await dishonest.room.emit("jade-avatar-state"); await dishonest.change("next");
  assert.equal(dishonest.selector.value, "classic", "a fulfilled promise alone is not evidence of a loaded model");
  assert.match(dishonest.status.textContent, /n’a pas pu être chargé/);

  for (const transport of ["reject", "http-error", "invalid-json", "timeout"]) {
    const a = client({transport});
    if (transport === "timeout") for (const fire of [...a.timers.values()]) fire();
    await a.ready;
    assert.equal(a.window.JadeModelCatalog.defaultId, "classic");
    assert.equal(a.window.JadeModelCatalog.get("classic").manifestUrl, "/model/Jade.model3.json");
    assert.equal(a.window.JadeModelCatalog.get("next").available, false);
    assert.equal(a.timers.size, 0, "catalogue timeout is always cleaned up");
  }

  const invalid = [
    data => {data.version = 2;},
    data => {data.defaultId = "classic";},
    data => {data.models[1].manifestUrl = "https://remote.invalid/Jade.model3.json";},
    data => {data.models[1].manifestUrl = "/models/next/../../private/Jade.model3.json";},
    data => {data.models[1].presentation = "seated";},
    data => {data.models[1].classicIntents = true;},
    data => {data.models[1].idleMotion = "Unknown";},
    data => {data.models[1].available = "true";},
    data => {data.models[1].id = "classic";},
    data => {data.models.pop();}
  ];
  for (const mutate of invalid) {
    const data = catalogue(true); mutate(data);
    const a = client({data}); await a.ready;
    assert.equal(a.window.JadeModelCatalog.get("next").available, false, "malformed catalogue uses safe classic fallback");
    assert.equal(a.window.JadeModelCatalog.get("classic").manifestUrl, "/model/Jade.model3.json");
  }
  const data = catalogue(true), immutable = client({data, withUi:false}); await immutable.ready;
  const catalog = immutable.window.JadeModelCatalog;
  assert(Object.isFrozen(catalog)); assert(Object.isFrozen(catalog.list()));
  for (const profile of catalog.list()) assert(Object.isFrozen(profile));
  assert.equal(catalog.get("unknown"), null);
  assert.throws(() => {catalog.get("next").manifestUrl = "https://remote.invalid/";}, TypeError);
  data.models[1].available = false;
  assert.equal(catalog.get("next").available, true, "validated catalogue does not retain mutable response objects");
  assert.equal(immutable.requests.length, 1);
  assert.equal(immutable.requests[0].url, "/assets/avatar-models.json", "initialization fetches metadata only");
  assert.equal(immutable.requests[0].options.mode, "same-origin");
  assert.equal(immutable.requests[0].options.credentials, "omit");

  const html = fs.readFileSync(path.join(web, "salon.html"), "utf8");
  const profileStart = html.indexOf('<section class="profile-intro"');
  assert(profileStart >= 0, "Profile section exists");
  // Profile contains nested sections, including the Live settings. Stop at its
  // matching closing tag, not at the end of the first nested section.
  let profile = "", depth = 0;
  for (const tag of html.slice(profileStart).matchAll(/<\/?section\b[^>]*>/g)) {
    depth += tag[0].startsWith("</") ? -1 : 1;
    if (depth === 0) {
      profile = html.slice(profileStart, profileStart + tag.index + tag[0].length);
      break;
    }
  }
  assert(profile, "Profile section has a matching closing tag");
  assert(profile.includes('id="avatar-model-selector"'), "model control belongs to Profile");
  assert.equal((html.match(/id="avatar-model-selector"/g) || []).length, 1);
  console.log("Avatar catalogue/UI: safe fallback, immutable profiles, no eager load, availability, selection and rollback PASS");
})().catch(error => {console.error(error); process.exitCode = 1;});
