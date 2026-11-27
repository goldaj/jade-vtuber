/* Only presentation settings survive reload; corrupt/blocked storage is safe. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../src/jade_runtime/mobile_web/preferences.js"), "utf8");
const key = "jade.mobile.preferences.v1";

function open(storage = new Map(), {readFails = false, writeFails = false, absent = false} = {}) {
  const window = {};
  if (!absent) Object.defineProperty(window, "localStorage", {get() {
    if (readFails) throw new Error("Storage disabled");
    return {
      getItem(name) { return storage.get(name) ?? null; },
      setItem(name, value) {
        if (writeFails) throw new Error("Quota exceeded");
        storage.set(name, value);
      }
    };
  }});
  vm.runInNewContext(source, {window});
  return window.JadePreferences;
}

const storage = new Map();
const first = open(storage);
assert.equal(first.get("soundEnabled", true), true);
assert.equal(first.get("avatarShakeEnabled", false), false);
const settings = {
  soundEnabled:false, notificationsEnabled:false, portraitMotionEnabled:false,
  avatarShakeEnabled:true, room:"kitchen", avatarModel:"classic", deploymentLevel:"error"
};
for (const [name, value] of Object.entries(settings)) assert.equal(first.set(name, value), true);
const second = open(storage);
for (const [name, value] of Object.entries(settings)) assert.equal(second.get(name), value, name + " survives reopening");
assert.equal(second.set("soundEnabled", true), true);
assert.equal(open(storage).get("soundEnabled"), true, "a later choice replaces the earlier one");
assert.equal(storage.size, 1, "settings use one bounded record");
assert.equal(second.set("room", "living"), true);
assert.equal(open(storage).get("room"), "living", "salon survives reopening");

for (const [name, value] of [
  ["token","private"], ["thread","chat"], ["liveSession","active"], ["identityId","123"],
  ["__proto__",{}], ["constructor",{}], ["soundEnabled","false"], ["room","remote"],
  ["avatarModel","../../secret"], ["deploymentLevel","debug"], ["notificationsEnabled",1]
]) assert.equal(second.set(name, value), false, "reject " + name);
assert.deepEqual(Object.keys(JSON.parse(storage.get(key)).values).sort(), Object.keys(settings).sort());

// Every stored field is checked on read too, not only on application writes.
storage.set(key, JSON.stringify({version:1,values:{soundEnabled:false,token:"secret",room:"evil",avatarModel:"classic"}}));
const scrubbed = open(storage);
assert.equal(scrubbed.get("soundEnabled", true), false);
assert.equal(scrubbed.get("room", "bedroom"), "bedroom");
assert.equal(scrubbed.get("token"), undefined);
scrubbed.set("deploymentLevel", "warning");
assert.equal(storage.get(key).includes("secret"), false);
assert.equal(storage.get(key).includes("evil"), false);

for (const invalid of ["{broken", "null", "[]", JSON.stringify({version:2,values:settings}),
  JSON.stringify({version:1,values:[]}), "x".repeat(4097)]) {
  const damaged = new Map([[key, invalid]]);
  const usable = open(damaged);
  assert.equal(usable.get("soundEnabled", true), true);
  assert.equal(usable.set("room", "kitchen"), true);
  assert.equal(open(damaged).get("room"), "kitchen");
}
for (const options of [{readFails:true}, {writeFails:true}, {absent:true}]) {
  const usable = open(new Map(), options);
  assert.equal(usable.get("soundEnabled", true), true);
  assert.equal(usable.set("soundEnabled", false), false, "unavailable persistence is reported without throwing");
  assert.equal(usable.get("soundEnabled", true), false, "current-session settings still work");
}

const shared = new Map();
const tabOne = open(shared), tabTwo = open(shared);
tabOne.set("room", "kitchen");
tabTwo.set("soundEnabled", false);
assert.equal(open(shared).get("room"), "kitchen", "independent tab changes preserve unrelated settings");
assert.equal(open(shared).get("soundEnabled"), false);
assert(Object.isFrozen(first));
console.log("Mobile preferences: reload, whitelist, defaults, invalid/blocked storage and cross-tab preservation PASS");
