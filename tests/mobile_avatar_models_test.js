/* r21 catalogue and selection contract without a renderer or network.
 * The historical slot remains metadata required by the two-slot schema only. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const web = path.join(__dirname, "../src/jade_runtime/mobile_web");
const source = fs.readFileSync(path.join(web, "avatar-models.js"), "utf8");
const preferencesSource = fs.readFileSync(path.join(web, "preferences.js"), "utf8");

function catalogue(nextAvailable = false) {
  return {version:1, defaultId:nextAvailable ? "next" : "classic", models:[
    {id:"classic", label:"Emplacement historique", available:true, manifestUrl:"/model/Jade.model3.json",
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

function client({data = catalogue(), transport = "ok", withUi = true, storage = new Map()} = {}) {
  const selector = new Element(), status = new Element(), room = new Element();
  const document = {
    getElementById(id) { return withUi ? {"avatar-model-selector":selector, "avatar-model-status":status}[id] : null; },
    querySelector() { return room; }, createElement() { return new Element(); }
  };
  const timers = new Map(), requests = [], selections = [], lifecycle = [];
  let nextTimer = 0, resolveFetch;
  const window = {
    localStorage:{getItem:key => storage.get(key) ?? null, setItem:(key, value) => storage.set(key, value)},
    JadeConversation:{stopForModelChange() {
      lifecycle.push("stop");
      return () => lifecycle.push("resume");
    }},
    setTimeout(callback, ms) { const id = ++nextTimer; timers.set(id, {callback, ms}); return id; },
    clearTimeout(id) { timers.delete(id); }
  };
  const fetch = async (url, options) => {
    const outcome = Array.isArray(transport) ? transport[requests.length] : transport;
    requests.push({url, options});
    assert.equal(url, "/assets/avatar-models.json", "catalogue code never loads model assets");
    if (outcome === "reject") throw new Error("unexpected fetch error");
    if (outcome === "network-error") throw new TypeError("Failed to fetch");
    if (outcome === "aborted") throw new DOMException("Load aborted", "AbortError");
    if (outcome === "pending" || outcome === "timeout") {
      await new Promise((resolve, reject) => {
        resolveFetch = resolve;
        options.signal.addEventListener("abort", () => reject(options.signal.reason), {once:true});
      });
    }
    const status = typeof outcome === "number" ? outcome : 200;
    return {status, ok:status === 200, async json(){
      if (outcome === "invalid-json") throw new SyntaxError("invalid JSON");
      return data;
    }};
  };
  const context = vm.createContext({window, document, fetch, AbortController, console});
  vm.runInContext(preferencesSource, context, {filename:"preferences.js"});
  vm.runInContext(source, context, {filename:"avatar-models.js"});
  function renderer(state = {status:"error", modelId:null, requestedId:"next", message:"r21 non chargé."}, select) {
    let currentState = state;
    const avatar = {get state(){return currentState;}, async selectModel(id){
      selections.push(id);
      assert.equal(id, "next", "selection scenarios cover r21 only");
      lifecycle.push("select");
      return select ? select(id, update) : false;
    }};
    function update(next) { currentState = next; return room.emit("jade-avatar-state"); }
    window.JadeAvatar = avatar;
    return {avatar, update};
  }
  return {window, selector, status, room, timers, requests, selections, lifecycle, renderer, storage,
    ready:window.JadeModelCatalog.ready,
    completeFetch(){resolveFetch();},
    fireTimer(ms) {
      const timer = [...timers].find(([, pending]) => pending.ms === ms);
      assert(timer, `expected a ${ms} ms catalogue timer`);
      const [id, {callback}] = timer;
      timers.delete(id);
      callback();
    },
    async change(id){selector.value = id; await selector.emit("change");}
  };
}

(async () => {
  const waiting = client({data:catalogue(true), transport:"pending"});
  assert.equal(waiting.selector.disabled, true, "selector waits for catalogue and renderer");
  assert.equal(waiting.selector.children[1].disabled, true, "r21 remains disabled until the catalogue is validated");
  assert.equal(waiting.selections.length, 0);
  const existing = waiting.renderer({status:"ready", modelId:"next", requestedId:"next", message:""});
  await waiting.room.emit("jade-avatar-state");
  assert.equal(waiting.selector.disabled, true, "renderer readiness alone cannot unlock an unknown catalogue");
  waiting.completeFetch(); await waiting.ready;
  assert.equal(waiting.selector.disabled, false);
  assert.equal(waiting.selector.value, "next");
  assert.equal(waiting.selector.children[1].textContent, "Jade actuelle (r21)");
  assert.equal(waiting.status.textContent, "");
  assert.equal(waiting.status.hidden, true, "successful settings do not add explanatory paragraphs");
  await waiting.change("next");
  assert.equal(waiting.selections.length, 0, "selecting the already displayed model does not reload it");
  await existing.update({status:"loading", modelId:"next", requestedId:"next", message:"Chargement…"});
  assert.equal(waiting.selector.disabled, true);
  assert.equal(waiting.status.textContent, "");
  await waiting.change("next");
  assert.equal(waiting.selections.length, 0, "a forced change during loading is ignored");

  const unavailable = client(); await unavailable.ready;
  unavailable.renderer(); await unavailable.room.emit("jade-avatar-state");
  assert.equal(unavailable.selector.children[1].textContent, "Jade actuelle (r21) — indisponible");
  assert.equal(unavailable.selector.children[1].disabled, true);
  await unavailable.change("next");
  assert.equal(unavailable.selections.length, 0, "unavailable r21 never reaches the renderer");
  assert.equal(unavailable.selector.value, "", "no loaded model is invented when r21 is unavailable");
  assert.match(unavailable.status.textContent, /pas encore disponible/);
  await unavailable.change("untrusted");
  assert.equal(unavailable.selections.length, 0, "unknown model never reaches the renderer");

  const available = client({data:catalogue(true)}); await available.ready;
  assert.equal(available.window.JadeModelCatalog.defaultId, "next");
  assert.equal(available.selector.disabled, true, "an available catalogue does not create a renderer");
  let finishSelection;
  available.renderer(undefined, async (id, update) => {
    await update({status:"loading", modelId:null, requestedId:id, message:"Chargement de r21…"});
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
  assert.equal(available.selector.value, "", "r21 is not displayed as ready while its loading is pending");
  await available.change("next");
  assert.deepEqual(available.selections, ["next"], "a pending selection cannot trigger another load");
  assert.deepEqual(available.lifecycle, ["stop", "select"]);
  finishSelection(); await change;
  assert.equal(available.selector.disabled, false);
  assert.equal(available.selector.value, "next");
  assert.equal(available.status.textContent, "");
  assert.equal(available.status.hidden, true);
  assert.equal(available.window.JadePreferences.get("avatarModel"), "next");
  assert.deepEqual(available.lifecycle, ["stop", "select", "resume"]);

  const failed = client({data:catalogue(true)}); await failed.ready;
  failed.renderer(undefined, async (id, update) => {
    await update({status:"loading", modelId:null, requestedId:id, message:"Chargement…"});
    await update({status:"error", modelId:null, requestedId:id, message:"Chargement de r21 impossible. Tu peux réessayer."});
    return false;
  });
  await failed.room.emit("jade-avatar-state"); await failed.change("next");
  assert.equal(failed.selector.value, "", "a failed r21 load cannot claim another model is displayed");
  assert.equal(failed.selector.disabled, false, "failure leaves the control available for another attempt");
  assert.equal(failed.status.textContent, "Chargement de r21 impossible. Tu peux réessayer.");
  assert.deepEqual(failed.lifecycle, ["stop", "select", "resume"]);
  assert.equal(failed.window.JadePreferences.get("avatarModel"), undefined, "a failed r21 load is not saved");

  const thrown = client({data:catalogue(true)}); await thrown.ready;
  thrown.renderer({status:"error", modelId:null, requestedId:"next", message:"Erreur précédente."},
    async () => { throw new Error("unexpected renderer failure"); });
  await thrown.room.emit("jade-avatar-state"); await thrown.change("next");
  assert.equal(thrown.selector.value, "");
  assert.match(thrown.status.textContent, /n’a pas pu être chargé/,
    "unexpected errors cannot retain an unrelated previous message");

  const dishonest = client({data:catalogue(true)}); await dishonest.ready;
  dishonest.renderer(undefined, async () => true);
  await dishonest.room.emit("jade-avatar-state"); await dishonest.change("next");
  assert.equal(dishonest.selector.value, "", "a fulfilled promise alone is not evidence of a loaded model");
  assert.match(dishonest.status.textContent, /n’a pas pu être chargé/);
  assert.equal(dishonest.window.JadePreferences.get("avatarModel"), undefined);

  const stored = new Map();
  const first = client({data:catalogue(true), storage:stored}); await first.ready;
  first.renderer(undefined, async (id, update) => {
    await update({status:"ready",modelId:id,message:""});
    return true;
  });
  await first.room.emit("jade-avatar-state");
  await first.change("next");
  const reopened = client({data:catalogue(true), storage:stored}); await reopened.ready;
  assert.equal(reopened.window.JadeModelCatalog.defaultId, "next", "reopening preserves a successful r21 choice");
  const missing = client({data:catalogue(false), storage:stored}); await missing.ready;
  assert.equal(missing.window.JadeModelCatalog.get("next").available, false);
  assert.equal(missing.requests.length, 1, "confirmed unavailability is not retried");
  assert.equal(missing.window.JadePreferences.get("avatarModel"), "next", "a temporary unavailability does not erase the user's choice");
  const recovered = client({data:catalogue(true), storage:stored}); await recovered.ready;
  assert.equal(recovered.window.JadeModelCatalog.defaultId, "next", "remembered model returns when available again");

  for (const transport of ["reject", 403, 404, "invalid-json"]) {
    const a = client({transport});
    await a.ready;
    assert.equal(a.window.JadeModelCatalog.get("next").available, false);
    assert.equal(a.requests.length, 1, "definitive errors are not retried");
    assert.equal(a.selections.length, 0, "catalogue failure never loads a substitute model");
    assert.equal(a.timers.size, 0, "catalogue timeout is always cleaned up");
  }

  const settle = () => new Promise(resolve => setImmediate(resolve));
  for (const failure of [502, 503, 504, "network-error", "aborted", "timeout"]) {
    const a = client({data:catalogue(true), transport:[failure, "ok"]});
    if (failure === "timeout") a.fireTimer(5000);
    await settle();
    assert.equal(a.requests.length, 1, "retry waits a short delay");
    a.fireTimer(250);
    await a.ready;
    assert.equal(a.requests.length, 2);
    assert.notEqual(a.requests[0].options.signal, a.requests[1].options.signal, "retry gets a fresh timeout");
    assert.equal(a.window.JadeModelCatalog.defaultId, "next", "r21 becomes available after a transient failure");
    assert.equal(a.timers.size, 0);
  }
  const classic = client({data:catalogue(true), transport:[503, "ok"]});
  classic.window.JadePreferences.set("avatarModel", "classic");
  await settle();
  classic.fireTimer(250);
  await classic.ready;
  assert.equal(classic.window.JadeModelCatalog.get("next").available, true);
  assert.equal(classic.window.JadeModelCatalog.defaultId, "classic", "recovery preserves explicit r20 selection");

  const exhausted = client({data:catalogue(true), transport:"timeout"});
  exhausted.fireTimer(5000);
  await settle();
  exhausted.fireTimer(250);
  await settle();
  exhausted.fireTimer(5000);
  await settle();
  assert.equal(exhausted.timers.size, 0, "a second failure leaves no retry or expiry timer");
  await exhausted.ready;
  assert.equal(exhausted.requests.length, 2, "a second failure ends retries");
  assert.equal(exhausted.window.JadeModelCatalog.get("next").available, false);

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
    assert.equal(a.window.JadeModelCatalog.get("next").available, false, "malformed catalogue cannot enable r21");
    assert.equal(a.selections.length, 0);
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
  console.log("Avatar catalogue/UI: r21 availability, selection, failures, persistence and metadata validation PASS");
})().catch(error => {console.error(error); process.exitCode = 1;});
