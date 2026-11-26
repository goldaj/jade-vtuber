/* Product integration with an inert Live double: no microphone or network. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const elements = new Map(), windows = {}, documents = {}, requests = [], stops = [], avatarEvents = [];
let serial = 0, liveOptions, toggles = 0, refreshes = 0, pendingClose = null;
function node(id) {
  const classes = new Set();
  return {id, value:"", textContent:"", disabled:false, hidden:false, children:[], handlers:{}, attrs:{}, dataset:{},
    classList:{add(...values) { values.forEach(value => classes.add(value)); },
      remove(...values) { values.forEach(value => classes.delete(value)); }, contains:value => classes.has(value),
      toggle(value, on) { if (on ?? !classes.has(value)) classes.add(value); else classes.delete(value); }},
    style:{setProperty() {}, removeProperty() {}},
    setAttribute(key, value) { this.attrs[key] = value; }, removeAttribute(key) { delete this.attrs[key]; },
    addEventListener(name, fn) { this.handlers[name] = fn; },
    append(...values) { values.forEach(value => this.appendChild(value)); },
    appendChild(value) { value.remove?.(); value.parentElement = this; this.children.push(value); return value; },
    insertBefore(value) { this.appendChild(value); },
    remove() { if (this.parentElement) this.parentElement.children = this.parentElement.children.filter(value => value !== this); this.parentElement = null; },
    replaceChildren() { this.children.forEach(value => { value.parentElement = null; }); this.children = []; },
    querySelector() { return element("fake-submit"); }, focus() {}, getBoundingClientRect() { return {width:640}; }};
}
function element(id) { if (!elements.has(id)) elements.set(id, node(id)); return elements.get(id); }
const shell = element("shell"); shell.dataset.view = "home";
const navigation = ["home", "chat", "profile"].map(view => {
  const value = element("nav-" + view); value.dataset.viewTarget = view; return value;
});
const document = {hidden:false, documentElement:{}, body:element("body"),
  getElementById:element, querySelectorAll:selector => selector === ".app-nav-item" ? navigation : [],
  querySelector:selector => ({".shell":shell, ".room-bottom":element("room-bottom"), ".room-plane":element("room-plane")})[selector] || null,
  createElement:tag => node(tag), addEventListener(name, fn) { documents[name] = fn; }};
const state = {mode:"live", revision:1, loaded:true, supported:true, available:true, capture:"closed",
  lease_state:"closed", session_state:"absent", session_id:null, active:false, changing:false, message:"",
  capabilities:{voice:{notice:"Voix de test explicite"}}};
function emitState(change = {}) { Object.assign(state, change); liveOptions.onState({...state}); }
const live = {
  get mode() { return state.mode; }, get active() { return state.active; },
  async refresh() { refreshes++; emitState(); },
  async setMode(mode) { emitState({mode, revision:state.revision + 1}); },
  async toggleMicrophone() {
    toggles++; emitState({active:!state.active, capture:state.active ? "closed" : "armed",
      lease_state:state.active ? "closed" : "armed"});
  },
  stop(reason) {
    stops.push(reason); emitState({active:false, capture:"closed", lease_state:"closed", session_state:"absent", session_id:null});
    return pendingClose || Promise.resolve();
  },
};
const window = {document, location:{hash:""}, crypto:{randomUUID:() => "thread-" + (++serial)},
  setTimeout, clearTimeout, addEventListener(name, fn) { (windows[name] ||= []).push(fn); },
  JadeLive:{create(options) { liveOptions = options; return live; }},
  JadeAvatar:{setMouth:value => avatarEvents.push(["mouth", value]), setSpeaking:value => avatarEvents.push(["speaking", value]),
    setIntent:(value, config) => avatarEvents.push(["intent", value, config]), resetIntent:() => avatarEvents.push(["reset"]),
    startReplyMotion:value => avatarEvents.push(["motion", value]), resize() {}},
  AudioContext:class { resume() { return Promise.resolve(); } },
};
const sandbox = {window, document, navigator:{}, crypto:window.crypto, performance:{now:() => 0},
  AbortController, setTimeout, clearTimeout, setInterval:() => 1, clearInterval() {},
  requestAnimationFrame:() => 1, cancelAnimationFrame() {}, URL, Blob, console,
  async fetch(url, options) {
    requests.push({url, options});
    if (url === "/api/chat") return {status:200, ok:true, json:async () => ({reply:"Réponse classique", intent:"neutral"})};
    return {status:200, ok:true, json:async () => ({enabled:false, subscriptions:[]})};
  }};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../src/jade_runtime/mobile_web/app.js"), "utf8"), sandbox);
const tick = () => new Promise(resolve => setImmediate(resolve));
const press = () => element("mic").handlers.pointerdown({button:0, isPrimary:true, pointerId:1, preventDefault() {}});

(async () => {
  window.JadeMobileApp.login("in-memory-token"); await tick();
  assert.equal(toggles, 0, "persisted Live preference after login never arms the microphone");
  assert.equal(element("live-mode-toggle").attrs["aria-pressed"], "true");
  assert.equal(element("live-voice-notice").textContent, "Voix de test explicite");
  assert.match(element("mic").attrs["aria-label"], /Commencer/);
  await press(); assert.equal(toggles, 1); assert.equal(state.active, true);
  element("mic").handlers.click({detail:1});
  assert.equal(toggles, 1, "the click after a pointer tap cannot toggle Live a second time");
  const stopCount = stops.length;
  for (const value of navigation) value.handlers.click();
  await element("fullscreen").handlers.click();
  await element("fullscreen").handlers.click();
  assert.equal(stops.length, stopCount, "navigation, profile refresh and fullscreen keep the same Live capture");
  assert.equal(toggles, 1); assert(refreshes >= 2);
  element("sound-toggle").handlers.click();
  assert.equal(stops.at(-1), "sound_off"); assert.equal(state.active, false);
  element("sound-toggle").handlers.click();
  assert.equal(toggles, 1, "sound ON does not restart Live");
  await press();

  liveOptions.onTranscript({session_id:"s1", replace:true, segments:[
    {segment_id:"user", role:"user", text:"Bonjour"},
    {segment_id:"reply", role:"assistant", text:"[INTENT:happy] Salut", status:"received"},
  ]});
  const log = element("messages");
  assert.equal(log.children.length, 2);
  assert.equal(log.children[1].children[0].textContent, "Salut");
  const reply = log.children[1];
  liveOptions.onTranscript({session_id:"s1", replace:true, segments:[
    {segment_id:"user", role:"user", text:"Bonjour Jade"},
    {segment_id:"reply", role:"assistant", text:"Salut, Goldaj", status:"interrupted"},
  ]});
  assert.equal(log.children.length, 2); assert.equal(log.children[1], reply, "fragments update a single bubble");
  assert.equal(reply.children[2].textContent, "Réponse interrompue");
  liveOptions.onTranscript({session_id:"s1", replace:true, segments:[
    {segment_id:"merged", role:"user", text:"Bonjour Jade"},
    {segment_id:"reply", role:"assistant", text:"Salut, Goldaj", status:"delivery_unknown"},
  ]});
  assert.equal(log.children.length, 2, "replacement removes a merged segment's old ghost bubble");
  liveOptions.onAttachments({session_id:"s1", attachments:[
    {name:"résumé.txt", url:"/api/documents/" + "a".repeat(32)},
    {name:"unsafe", url:"https://outside.test/private"},
  ]});
  assert.equal(reply.children.length, 3, "documents do not get attributed to the previous spoken reply");
  assert.equal(log.children.length, 3); assert.match(log.children[2].children[0].textContent, /résumé.txt/);
  liveOptions.onAttachments({session_id:"s1", attachments:[{name:"résumé.txt", url:"/api/documents/" + "a".repeat(32)}]});
  assert.equal(log.children[2].children.length, 1, "replayed action results do not duplicate download controls");
  liveOptions.onPlayback(.4, true);
  assert.deepEqual(avatarEvents.at(-1), ["speaking", true]);
  liveOptions.onIntent("tender");
  assert.equal(avatarEvents.at(-1)[0], "intent");
  assert.equal(avatarEvents.at(-1)[2].deferMotion, false, "Live does not add the classic 200 ms facial delay");

  let resolveClose;
  pendingClose = new Promise(resolve => { resolveClose = resolve; });
  element("message").value = "Par écrit";
  const text = element("composer").handlers.submit({preventDefault() {}});
  assert.equal(stops.at(-1), "text");
  assert.equal(requests.filter(value => value.url === "/api/chat").length, 0, "text waits for the bounded close request");
  pendingClose = null; resolveClose(); await text;
  assert.equal(requests.filter(value => value.url === "/api/chat").length, 1);
  assert.equal(toggles, 2, "a written reply never rearms Live");
  const previousThread = liveOptions.getThread();
  element("new-chat").handlers.click();
  assert.equal(stops.at(-1), "new_thread"); assert.notEqual(liveOptions.getThread(), previousThread);
  assert.equal(log.children.length, 0);
  await press(); document.hidden = true; documents.visibilitychange();
  assert.equal(stops.at(-1), "background"); document.hidden = false; documents.visibilitychange();
  assert.equal(toggles, 3, "returning foreground requires a new gesture");
  await element("mic").handlers.click({detail:0});
  assert.equal(toggles, 4, "assistive technology activation works without pointer or key events");
  const finishModel = window.JadeConversation.stopForModelChange();
  assert.equal(stops.at(-1), "model_change"); finishModel();
  emitState({available:false});
  assert.equal(element("live-mode-toggle").disabled, false, "OFF remains accessible after an admission failure");
  element("live-mode-toggle").handlers.click(); await tick();
  assert.equal(state.mode, "classic"); assert.equal(element("mic").disabled, false);
  assert.equal(element("mic").attrs["aria-label"], "Maintenir pour parler");
  const resets = avatarEvents.filter(event => event[0] === "reset").length;
  await live.refresh();
  assert.equal(avatarEvents.filter(event => event[0] === "reset").length, resets,
    "a read-only Profile refresh must not reset the classic avatar's current reply");
  console.log("Mobile Live app: profile, navigation, exclusive text/audio, transcripts and lifecycle PASS (inert client)");
})().catch(error => { console.error(error); process.exitCode = 1; });
