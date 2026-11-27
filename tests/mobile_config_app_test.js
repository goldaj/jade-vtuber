/* Settings integration: real preference store, inert audio, mocked private API. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const web = path.join(__dirname, "../src/jade_runtime/mobile_web");
const tick = () => new Promise(resolve => setImmediate(resolve));

function harness(storage = new Map(), device = {permission:"default", subscription:null}) {
  const elements = new Map(), requests = [], stops = [], intervals = [];
  let serial = 0, permissionRequests = 0, audioContexts = 0, captureRequests = 0, subscribeFailure = false;
  let discordEnabled = true, discordFailure = false;
  let options;
  function node(id) {
    const classes = new Set();
    return {id, value:"", checked:false, disabled:false, hidden:false, open:false, textContent:"", children:[],
      scrollHeight:300, scrollTop:0, handlers:{}, attrs:{}, dataset:{},
      classList:{add(...items) { items.forEach(item => classes.add(item)); },
        remove(...items) { items.forEach(item => classes.delete(item)); }, contains:item => classes.has(item),
        toggle(item, on) { if (on ?? !classes.has(item)) classes.add(item); else classes.delete(item); }},
      style:{setProperty() {}, removeProperty() {}},
      addEventListener(name, handler) { this.handlers[name] = handler; },
      setAttribute(name, value) { this.attrs[name] = value; }, removeAttribute(name) { delete this.attrs[name]; },
      appendChild(child) { child.parentElement = this; this.children.push(child); return child; },
      append(...children) { children.forEach(child => this.appendChild(child)); },
      insertBefore(child) { this.appendChild(child); }, replaceChildren() { this.children = []; },
      querySelector() { return element("fake-submit"); }, focus() {}, getBoundingClientRect() { return {width:393}; }};
  }
  function element(id) { if (!elements.has(id)) elements.set(id, node(id)); return elements.get(id); }
  const shell = element("shell"); shell.dataset.view = "home";
  const navigation = ["home", "chat", "reminders", "profile"].map(view => {
    const control = element("nav-" + view); control.dataset.viewTarget = view; return control;
  });
  // Removed controls really are absent, rather than accidentally manufactured
  // by the DOM double. Any surviving unguarded listener fails at startup.
  const removed = new Set(["notifications-on", "notifications-off", "deployment-autoscroll",
    "deployment-logs-load", "billing-refresh", "live-voice-notice"]);
  const document = {hidden:false, documentElement:{}, body:element("body"),
    getElementById:id => removed.has(id) ? null : element(id),
    querySelectorAll:selector => selector === ".app-nav-item" ? navigation : [],
    querySelector:selector => ({".shell":shell, ".room-bottom":element("room-bottom")})[selector] || null,
    createElement:node, addEventListener() {}};
  function subscription() {
    return {endpoint:"https://push.example.test/device", toJSON() { return {endpoint:this.endpoint, keys:{p256dh:"test", auth:"test"}}; },
      async unsubscribe() { device.subscription = null; return true; }};
  }
  const registration = {pushManager:{async getSubscription() { return device.subscription; },
    async subscribe() { return device.subscription = subscription(); }}};
  const Notification = {get permission() { return device.permission; },
    async requestPermission() { permissionRequests++; return device.permission; }};
  const navigator = {serviceWorker:{ready:Promise.resolve(registration), register:async () => registration, addEventListener() {}},
    mediaDevices:{getUserMedia() { captureRequests++; throw new Error("unexpected microphone"); }}};
  const state = {mode:"live", revision:0, loaded:true, supported:true, available:true, capture:"closed",
    lease_state:"closed", session_state:"absent", session_id:null, active:false, changing:false, message:""};
  const emit = change => { Object.assign(state, change); options?.onState({...state}); };
  const live = {get state() { return {...state}; }, get mode() { return state.mode; }, get active() { return state.active; },
    async refresh() { emit({}); }, async setMode(mode) { emit({mode}); },
    async stop(reason) { stops.push(reason); emit({active:false, capture:"closed", lease_state:"closed"}); }};
  const interval = fn => { intervals.push(fn); return intervals.length; };
  const window = {document, navigator, location:{hash:""}, crypto:{randomUUID:() => "thread-" + (++serial)},
    isSecureContext:true, PushManager:class {}, Notification,
    localStorage:{getItem:key => storage.get(key) ?? null, setItem:(key, value) => storage.set(key, value)},
    setTimeout, clearTimeout, setInterval:interval, clearInterval() {}, addEventListener() {},
    JadeAvatar:{setMouth() {}, setSpeaking() {}, setIntent() {}, resetIntent() {}, resize() {}},
    JadeLive:{create(value) { options = value; return live; }},
    AudioContext:class { constructor() { audioContexts++; } }};
  const sandbox = {window, document, navigator, Notification, crypto:window.crypto,
    performance:{now:() => 0}, AbortController, URL, Blob, console,
    setTimeout, clearTimeout, setInterval:interval, clearInterval() {},
    requestAnimationFrame:() => 1, cancelAnimationFrame() {},
    atob:value => Buffer.from(value, "base64").toString("binary"),
    async fetch(url, request = {}) {
      const body = request.body ? JSON.parse(request.body) : null;
      requests.push({url, body, request});
      let result = {};
      if (url === "/api/push") {
        if (body.action === "config") result = {enabled:true, vapid_public_key:"dGVzdA"};
        if (body.action === "subscribe" && subscribeFailure)
          return {status:503, ok:false, json:async () => ({message:"Inscription refusée"})};
      } else if (url === "/api/chat") result = {reply:"Réponse silencieuse", intent:"neutral"};
      else if (url === "/control/api/status") result = {phase:"idle", branch:"develop", pycharm_run:true, running:true};
      else if (url === "/control/api/logs") result = {text:"INFO Started\nWARNING Warning\nERROR Failure"};
      else if (url === "/api/billing") result = {status:"ok", today:{usd:"1.25"}, month:{usd:"12.50"}, checked_at:"2026-11-27T08:00:00Z"};
      else if (url === "/api/discord/live") {
        if (body && discordFailure) return {status:503, ok:false, json:async () => ({error:"unavailable"})};
        if (body) discordEnabled = body.enabled;
        result = {enabled:discordEnabled, minutes:12.5, month:"2026-11", partial:true};
      }
      return {status:200, ok:true, json:async () => result};
    }};
  const context = vm.createContext(sandbox);
  for (const filename of ["preferences.js", "app.js"])
    vm.runInContext(fs.readFileSync(path.join(web, filename), "utf8"), context, {filename});
  async function change(id, checked) {
    element(id).checked = checked;
    element(id).handlers.change();
    await tick();
  }
  return {window, element, requests, stops, state, emit, storage, device, change,
    get options() { return options; }, get permissionRequests() { return permissionRequests; },
    get audioContexts() { return audioContexts; }, get captureRequests() { return captureRequests; },
    set subscribeFailure(value) { subscribeFailure = value; },
    set discordFailure(value) { discordFailure = value; },
    async login() { window.JadeMobileApp.login("private-in-memory-bearer"); await tick(); },
    async config() { element("nav-profile").handlers.click(); await tick(); }};
}

(async () => {
  const first = harness(); await first.login();
  assert.equal(first.element("sound-toggle").checked, true, "voice is enabled for a new installation");
  first.emit({active:true, capture:"armed", lease_state:"armed"});
  await first.change("sound-toggle", false);
  assert.equal(first.options.getSoundEnabled(), false);
  assert.equal(first.stops.at(-1), "sound_off", "unchecking voice stops active Live audio");
  assert.equal(first.state.active, false);

  const restored = harness(first.storage, first.device); await restored.login();
  assert.equal(restored.element("sound-toggle").checked, false, "closing and opening keeps the unchecked choice");
  assert.equal(restored.options.getSoundEnabled(), false, "the restored choice controls the audio path, not only the checkbox");
  restored.element("message").value = "Bonjour";
  await restored.element("composer").handlers.submit({preventDefault() {}});
  const chat = restored.requests.find(request => request.url === "/api/chat");
  assert.equal(chat.body.speak, false, "silent preference is sent to the existing chat transport");
  await restored.change("sound-toggle", true);
  assert.equal(restored.options.getSoundEnabled(), true);
  assert.equal(restored.state.active, false, "checking voice cannot resume a previous microphone session");
  assert.equal(restored.audioContexts, 0); assert.equal(restored.captureRequests, 0);
  assert.equal(harness(restored.storage, restored.device).element("sound-toggle").checked, true);
  assert(![...first.storage.values()].join("").includes("private-in-memory-bearer"), "no authentication token is persisted");

  await restored.config();
  assert.equal(restored.permissionRequests, 0, "opening Config never prompts for permission");
  assert.equal(restored.element("notifications-enabled").checked, false);
  restored.device.permission = "denied";
  await restored.change("notifications-enabled", true);
  assert.equal(restored.element("notifications-enabled").checked, false, "denied permission restores the confirmed checkbox");
  assert.equal(restored.element("notification-status").hidden, false, "a failed explicit action remains visible");
  restored.device.permission = "granted";
  restored.subscribeFailure = true;
  await restored.change("notifications-enabled", true);
  assert.equal(restored.element("notifications-enabled").checked, false, "server registration failure cannot enable the setting");
  assert.equal(restored.device.subscription, null, "a newly created browser subscription is cleaned up after server failure");
  assert.equal(restored.window.JadePreferences.get("notificationsEnabled"), false);
  restored.subscribeFailure = false;
  await restored.change("notifications-enabled", true);
  assert.equal(restored.element("notifications-enabled").checked, true);
  assert.equal(restored.element("notification-status").hidden, true, "success adds no permanent notification paragraph");
  assert.equal(restored.window.JadePreferences.get("notificationsEnabled"), true);
  const reopened = harness(restored.storage, restored.device); await reopened.login(); await reopened.config();
  assert.equal(reopened.element("notifications-enabled").checked, true);
  assert.equal(reopened.permissionRequests, 0, "restoring notifications does not request permission again");
  await reopened.change("notifications-enabled", false);
  assert.equal(reopened.device.subscription, null);
  assert.equal(reopened.window.JadePreferences.get("notificationsEnabled"), false);
  const disabled = harness(reopened.storage, reopened.device); await disabled.login(); await disabled.config();
  assert.equal(disabled.element("notifications-enabled").checked, false);
  assert.equal(disabled.permissionRequests, 0, "disabled notifications stay disabled after reopening");

  disabled.element("deployment-panel").open = true;
  await disabled.element("deployment-load").handlers.click();
  assert.equal(disabled.element("deployment-logs").scrollTop, 300, "new logs always scroll to the bottom");
  disabled.element("deployment-level").value = "error";
  disabled.element("deployment-level").handlers.change();
  assert.equal(disabled.element("deployment-logs").textContent, "ERROR Failure");
  assert.equal(harness(disabled.storage, disabled.device).element("deployment-level").value, "error", "log filter also survives reopening");
  disabled.element("billing-panel").open = true;
  disabled.element("billing-panel").handlers.toggle(); await tick();
  assert.equal(disabled.element("billing-today").textContent, "1.25 USD");
  assert.equal(disabled.element("billing-month").textContent, "12.50 USD");
  assert.match(disabled.element("billing-status").textContent, /Dernière actualisation/);
  assert(!disabled.element("billing-status").textContent.includes("reportées"));

  const discordPanel = disabled.element("discord-live-panel"), discordToggle = disabled.element("discord-live-enabled");
  discordPanel.open = true;
  discordPanel.handlers.toggle(); await tick();
  const discordRead = disabled.requests.find(request => request.url === "/api/discord/live");
  assert.equal(discordRead.request.method, "GET");
  assert.equal(discordRead.request.headers.Authorization, "Bearer private-in-memory-bearer");
  assert.equal(discordToggle.checked, true);
  assert.equal(discordToggle.disabled, false);
  assert.equal(disabled.element("discord-live-minutes").textContent, "12,5");
  assert.match(disabled.element("discord-live-status").textContent, /partiel/);

  await disabled.change("discord-live-enabled", false);
  const discordWrite = disabled.requests.at(-1);
  assert.equal(discordWrite.url, "/api/discord/live");
  assert.equal(discordWrite.request.method, "POST");
  assert.deepEqual(discordWrite.body, {enabled:false});
  assert.equal(discordToggle.checked, false);
  assert.equal(disabled.state.mode, "live", "Discord has a separate voice choice from mobile");
  await disabled.login();
  assert.equal(discordToggle.checked, false, "the server choice is restored after authentication");

  disabled.discordFailure = true;
  await disabled.change("discord-live-enabled", true);
  assert.equal(discordToggle.checked, false, "a failure restores the last confirmed choice");
  assert.match(disabled.element("discord-live-status").textContent, /Impossible de confirmer/);
  disabled.discordFailure = false;
  await disabled.change("discord-live-enabled", true);
  assert.equal(discordToggle.checked, true);
  console.log("Mobile Config: sound, notifications, deployment logs, billing and Discord follow-up PASS");
})().catch(error => { console.error(error); process.exitCode = 1; });
