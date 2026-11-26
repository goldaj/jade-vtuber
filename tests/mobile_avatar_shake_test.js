"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../src/jade_runtime/mobile_web/avatar-shake.js"), "utf8");

class Target {
  constructor() { this.listeners = new Map(); }
  addEventListener(type, listener) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type).add(listener);
  }
  removeEventListener(type, listener) { this.listeners.get(type)?.delete(listener); }
  count(type) { return this.listeners.get(type)?.size ?? 0; }
  async dispatch(type, data) {
    await Promise.all([...(this.listeners.get(type) ?? [])].map(listener => listener(data)));
  }
}

function createClient({motion = {}, secure = true, reduced = false} = {}) {
  const document = new Target();
  const window = new Target();
  const control = new Target();
  const status = {textContent:""};
  const room = new Target();
  const fullscreen = new Set();
  const shell = {dataset:{view:"profile"}, classList:{contains:name => fullscreen.has(name)}};
  const media = Object.assign(new Target(), {matches:reduced});
  const orientation = Object.assign(new Target(), {angle:0});
  const state = {modelId:"next",status:"ready"};
  const impulses = [];
  const timers = new Set();
  let stopCount = 0;
  document.hidden = false;
  document.getElementById = id => ({
    "avatar-shake-enabled":control, "avatar-shake-status":status,
  })[id];
  document.querySelector = name => ({".shell":shell, ".room":room})[name];
  Object.assign(window, {
    DeviceMotionEvent:motion, isSecureContext:secure, matchMedia:() => media,
    screen:{orientation},
    JadeAvatar:{state, nudgeFromShake(x,y){impulses.push([x,y]);return true;}, stopShake(){stopCount++;}},
    setTimeout(callback){timers.add(callback);return callback;},
    clearTimeout(callback){timers.delete(callback);},
  });
  vm.runInNewContext(source, {document, window});
  return {
    window, status, control, impulses, orientation, state,
    get stopCount(){return stopCount;},
    view(view, immersive = false) {
      shell.dataset.view = view;
      if (immersive) fullscreen.add("is-room-only");
      else fullscreen.delete("is-room-only");
      return room.dispatch("jade-avatar-framing");
    },
    toggle(on) {
      control.checked = on;
      return control.dispatch("change");
    },
    visible(show) {
      document.hidden = !show;
      return document.dispatch("visibilitychange");
    },
    motion(time, x, y, z, raw = false) {
      const axis = {x,y,z};
      return window.dispatch("devicemotion", {
        timeStamp:time, [raw ? "accelerationIncludingGravity" : "acceleration"]:axis,
      });
    },
    sample(time, acceleration, accelerationIncludingGravity) {
      return window.dispatch("devicemotion", {timeStamp:time, acceleration, accelerationIncludingGravity});
    },
    runTimers() { for (const timer of [...timers]) { timers.delete(timer); timer(); } },
    reduce(on) { media.matches = on; return media.dispatch("change"); },
    avatarChanged() { return room.dispatch("jade-avatar-state"); },
  };
}

(async () => {
  const session = createClient();
  assert(!session.control.checked, "motion is opt-in");
  assert.match(session.status.textContent, /Active le réglage/, "instructions replace the HTML loading status");
  await session.toggle(true);
  assert.equal(session.window.count("devicemotion"), 0, "the Profile does not subscribe");
  await session.view("home");
  assert.equal(session.window.count("devicemotion"), 1);
  assert.match(session.status.textContent, /En attente des données/);
  session.runTimers();
  assert.match(session.status.textContent, /Aucune donnée.+Capteurs de mouvement/);
  await session.motion(0, 1, 0, 0);
  assert.match(session.status.textContent, /Capteur de mouvement actif/, "a late sample clears the warning");
  for (let pulse = 0; pulse < 4; pulse++)
    await session.motion(80 + pulse * 220, pulse % 2 ? 6 : -6, 2, 0);
  assert.equal(session.impulses.length, 0, "routine motion cannot shake Jade");
  await session.motion(1000, 14, 0, 0);
  await session.motion(1015, -15, 0, 0);
  assert.equal(session.impulses.length, 0, "ignore a near-instant spike");
  await session.motion(1025, -16, 0, 0);
  assert.equal(session.impulses.length, 1, "a fast deliberate reversal triggers one impulse");
  assert.deepEqual(session.impulses[0], [-1, 0], "a strong peak commands the full amplitude");
  await session.motion(1050, 0, 0, 0);
  assert.equal(session.status.textContent, "Secousse détectée.", "following sensor samples preserve the result");
  await session.motion(1270, 17, 0, 0);
  await session.motion(1345, -18, 0, 0);
  assert.equal(session.impulses.length, 1, "cooldown stops a second trigger in the same shake");
  await session.motion(2000, 0, 0, 16);
  await session.motion(2100, 0, 0, -17);
  assert.equal(session.impulses.length, 2, "forward/backward shakes produce a pitch impulse");
  assert(Math.abs(session.impulses[1][1]) > .5);
  await session.view("profile");
  assert.equal(session.status.textContent, "Secousse détectée.", "the result remains visible in Profile");
  await session.view("home");
  const beforeHide = session.stopCount;
  await session.visible(false);
  assert.equal(session.window.count("devicemotion"), 0, "pause the sensor while hidden");
  assert(session.stopCount > beforeHide);
  await session.visible(true);
  await session.view("chat");
  assert.equal(session.window.count("devicemotion"), 0, "Chat does not use motion data");
  await session.view("chat", true);
  assert.equal(session.window.count("devicemotion"), 1, "fullscreen listens from any tab");
  await session.reduce(true);
  assert.equal(session.window.count("devicemotion"), 0);
  assert.match(session.status.textContent, /mouvement réduit/);
  await session.reduce(false);
  session.state.modelId = "classic";
  await session.avatarChanged();
  assert.equal(session.window.count("devicemotion"), 0, "r20 has no shake response");

  const raw = createClient();
  await raw.toggle(true);
  await raw.view("home");
  for (let frame = 0; frame < 15; frame++) await raw.motion(frame * 40, 0, 0, 9.81, true);
  assert.equal(raw.impulses.length, 0, "gravity is not a shake");
  await raw.motion(700, 18, 0, 9.81, true);
  await raw.motion(780, -18, 0, 9.81, true);
  assert.equal(raw.impulses.length, 1, "raw accelerometer works with a gravity estimate");
  await raw.motion(1750, 14, 0, 0);
  raw.orientation.angle = 90;
  await raw.orientation.dispatch("change");
  await raw.motion(1830, -16, 0, 0);
  assert.equal(raw.impulses.length, 1, "a rotation resets the pending peak");
  await raw.motion(1900, 16, 0, 0);
  assert.equal(raw.impulses.length, 2);
  assert(Math.abs(raw.impulses[1][0]) < 1e-6 && raw.impulses[1][1] > .8, "landscape rotates the impulse axes");
  await raw.toggle(false);
  assert.equal(raw.window.count("devicemotion"), 0);
  assert.match(raw.status.textContent, /désactivée/);

  const sparse = createClient();
  await sparse.toggle(true);
  await sparse.view("home");
  await sparse.motion(0, 0, null, 9.81, true);
  await sparse.sample(100, {x:null, y:0, z:null}, {x:9, y:null, z:9.81});
  await sparse.sample(460, {x:null, y:0, z:null}, {x:-9, y:null, z:9.81});
  assert.equal(sparse.impulses.length, 1, "partly missing axes and a sparse reversal use the gravity-corrected data");
  assert(sparse.impulses[0][0] < -.6, "the weaker detected shake still has clear strength");
  await sparse.sample(1500, {x:0, y:0, z:0}, {x:1, y:null, z:9.81});
  await sparse.sample(1600, {x:0, y:0, z:0}, {x:15, y:null, z:9.81});
  assert.equal(sparse.impulses.length, 1, "a strong single jolt is ignored");
  await sparse.sample(1700, {x:.1, y:0, z:0}, {x:-15, y:null, z:9.81});
  assert.deepEqual(sparse.impulses[1], [-1, 0], "raw peaks recover an Android-style frozen linear channel");

  let grant;
  const permission = createClient({motion:{requestPermission:() => new Promise(resolve => { grant = resolve; })}});
  await permission.view("home");
  const waiting = permission.toggle(true);
  assert.equal(permission.window.count("devicemotion"), 0, "wait for explicit platform permission");
  await permission.toggle(false);
  grant("granted");
  await waiting;
  assert.equal(permission.window.count("devicemotion"), 0, "a late grant cannot reopen a disabled sensor");
  const declined = createClient({motion:{async requestPermission(){return "denied";}}});
  await declined.toggle(true);
  assert(!declined.control.checked && declined.window.count("devicemotion") === 0);
  assert.match(declined.status.textContent, /refusé/);
  const unavailable = createClient({motion:null});
  assert(unavailable.control.disabled && unavailable.window.count("devicemotion") === 0);
  assert.match(unavailable.status.textContent, /indisponible/);

  console.log("Avatar shake: opt-in, motion filtering, gravity fallback, cooldown and scene scoping PASS");
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
