"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../src/jade_runtime/mobile_web/avatar-gestures.js"), "utf8");

class Element {
  constructor(parent = null) {
    this.parent = parent;
    this.style = {};
    this.dataset = {};
    this.hidden = false;
    this.listeners = new Map();
    this.captures = new Set();
    const classes = new Set();
    this.classList = {add:name => classes.add(name), remove:name => classes.delete(name),
      contains:name => classes.has(name)};
  }
  addEventListener(type, listener) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(listener);
  }
  dispatch(type, attributes = {}) {
    const event = {type, target:this, defaultPrevented:false,
      preventDefault(){this.defaultPrevented = true;}, ...attributes};
    for (const listener of this.listeners.get(type) || []) listener(event);
    return event;
  }
  contains(target) { return target === this || (target?.parent != null && this.contains(target.parent)); }
  setPointerCapture(id) { this.captures.add(id); }
  hasPointerCapture(id) { return this.captures.has(id); }
  releasePointerCapture(id) {
    this.captures.delete(id);
    this.dispatch("lostpointercapture", {pointerId:id});
  }
}

function client({haptics = true} = {}) {
  const document = new Element(), window = new Element(), shell = new Element();
  const room = new Element(shell), zone = new Element(room), recenter = new Element(room);
  const microphone = new Element(room);
  shell.dataset.view = "home";
  room.dataset.room = "bedroom";
  Object.assign(room, {clientWidth:280, clientHeight:320, clientLeft:1, clientTop:2,
    getBoundingClientRect:() => ({left:10, top:30})});
  document.querySelector = selector => ({".room":room, ".shell":shell})[selector];
  document.getElementById = id => ({"avatar-recenter":recenter, "avatar-touch-zone":zone})[id];

  const timers = new Map(), frames = [];
  const calls = {moves:[], zooms:[], vibrations:[], resets:0};
  let clock = 1000, timerId = 0;
  window.setTimeout = (callback, ms) => {
    const id = ++timerId;
    timers.set(id, {callback, due:clock + ms});
    return id;
  };
  window.clearTimeout = id => timers.delete(id);
  window.requestAnimationFrame = callback => frames.push(callback);
  const state = {modelId:"next", status:"ready"};
  const avatar = window.JadeAvatar = {
    state, getTouchFrame:() => ({left:80, top:100, right:230, bottom:550}),
    isModelAt:(x, y) => x >= 86 && x <= 200 && y >= 110 && y <= 300,
    moveView:(x, y) => calls.moves.push([x, y]),
    zoomView:(value, x, y) => calls.zooms.push([value, x, y]),
    resetView:() => {calls.resets++;}
  };
  const navigator = haptics ? {vibrate:value => calls.vibrations.push(value)} : {};
  let observer;
  vm.runInNewContext(source, {window, document, navigator,
    ResizeObserver:class {constructor(callback){observer = callback;} observe(){}}
  }, {filename:"avatar-gestures.js"});

  function advance(ms) {
    clock += ms;
    for (const [id, {callback, due}] of timers) if (clock >= due) {
      timers.delete(id);
      callback();
    }
  }
  function frame() {
    for (const callback of frames.splice(0)) callback();
  }
  function pointer(type, opts = {}) {
    const {target = zone, ...attributes} = opts;
    const event = {pointerType:"touch", pointerId:1, isPrimary:true, clientX:100, clientY:160,
      timeStamp:clock, target, ...attributes};
    if (type === "pointerdown") document.dispatch(type, event);
    return target.dispatch(type, event);
  }
  function view(value, fullscreen = false) {
    shell.dataset.view = value;
    if (fullscreen) shell.classList.add("is-room-only");
    else shell.classList.remove("is-room-only");
    room.dispatch("jade-avatar-framing");
    frame();
  }
  function model(value) {
    state.modelId = value;
    room.dispatch("jade-avatar-state");
    frame();
  }
  return {window, document, zone, recenter, microphone, calls, avatar, advance, pointer, frame, view, model,
    resize(){observer(); frame();}, ignores(event){return window.JadeAvatarGestures.shouldIgnoreFullscreenTap(event);}};
}

const single = client();
assert.deepEqual(single.zone.style, {left:"53px", top:"52px", width:"182px", height:"268px"},
  "zone coordinates stay relative to the visible room and account for its border");
single.pointer("pointerdown");
single.advance(65);
assert.equal(single.ignores(single.pointer("pointerup")), false, "a short tap can still enter fullscreen");
single.advance(1500);
assert.deepEqual(single.calls.vibrations, []);

const drag = client();
drag.pointer("pointerdown");
assert(drag.zone.hasPointerCapture(1), "the finger is tracked beyond the avatar");
assert(drag.zone.dispatch("touchstart", {cancelable:true, changedTouches:[{clientX:100, clientY:160}]}).defaultPrevented,
  "a touch on Jade suppresses the WebView long press before its timer starts");
assert(!drag.zone.dispatch("touchstart", {cancelable:true, changedTouches:[{clientX:75, clientY:160}]}).defaultPrevented,
  "the transparent area around Jade does not claim native touch behavior");
assert.equal(drag.pointer("contextmenu").defaultPrevented, true, "a browser popup must not interrupt an avatar hold");
drag.advance(1199);
assert(!drag.zone.classList.contains("is-grabbed"));
drag.advance(1);
assert(drag.zone.classList.contains("is-grabbed"));
assert.deepEqual(drag.calls.vibrations, [20]);
drag.pointer("pointermove", {clientX:248, clientY:322});
drag.advance(500);
const release = drag.pointer("pointerup", {clientX:251, clientY:328});
assert(release.defaultPrevented);
assert(drag.ignores(release), "releasing Jade cannot also toggle fullscreen");
assert.deepEqual(drag.calls.moves, [[148, 162], [3, 6]], "Jade follows the finger up to the release coordinates");
assert.deepEqual(drag.calls.vibrations, [20], "only one confirmation per hold");
assert(!drag.zone.classList.contains("is-grabbed"));
assert(drag.ignores(drag.pointer("dblclick", {clientX:251, clientY:328})), "ignore the compatibility dblclick");
assert(!drag.ignores(drag.pointer("dblclick", {pointerType:"mouse", clientX:251, clientY:328})));
drag.recenter.dispatch("click");
assert.equal(drag.calls.resets, 1);

const pinch = client();
const second = {pointerId:2, isPrimary:false, clientX:220};
pinch.pointer("pointerdown");
pinch.advance(300);
pinch.pointer("pointerdown", second);
pinch.pointer("pointermove", {...second, clientX:250});
assert.deepEqual(pinch.calls.zooms, [[1.25, 160, 160]]);
assert.deepEqual(pinch.calls.moves, [[15, 0]]);
pinch.advance(1300);
assert.deepEqual(pinch.calls.vibrations, [], "pinching cancels the pending long press");
assert(pinch.ignores(pinch.pointer("pointerup", {...second, clientX:250})));
pinch.pointer("pointermove", {clientX:120});
assert(pinch.ignores(pinch.pointer("pointerup", {clientX:120})));
assert.deepEqual(pinch.calls.moves, [[15, 0]], "the remaining finger cannot drag Jade after a pinch");

const early = client();
early.pointer("pointerdown");
early.pointer("pointermove", {clientX:111});
early.pointer("pointermove", {clientX:100});
early.advance(1300);
assert.deepEqual(early.calls.vibrations, [], "leaving the hold tolerance cancels a hold even after returning");
early.pointer("pointerup");
early.pointer("pointerdown", {clientX:75});
early.advance(1300);
assert.deepEqual(early.calls.vibrations, [], "a press on transparent scenery cannot grab Jade");

const visualOnly = client({haptics:false});
visualOnly.pointer("pointerdown");
visualOnly.advance(1200);
assert(visualOnly.zone.classList.contains("is-grabbed"), "visual feedback remains available without vibration");
visualOnly.pointer("pointerup");
assert(!visualOnly.zone.classList.contains("is-grabbed"));

for (const interruption of ["microphone", "rotation", "cancel", "lostcapture", "classic", "chat", "hidden"]) {
  const interrupted = client();
  interrupted.pointer("pointerdown");
  if (interruption === "microphone")
    interrupted.pointer("pointerdown", {pointerId:2, isPrimary:false, target:interrupted.microphone});
  else if (interruption === "rotation") interrupted.resize();
  else if (interruption === "cancel") interrupted.pointer("pointercancel");
  else if (interruption === "lostcapture") interrupted.zone.releasePointerCapture(1);
  else if (interruption === "classic") interrupted.model("classic");
  else if (interruption === "chat") interrupted.view("chat");
  else {
    interrupted.document.hidden = true;
    interrupted.document.dispatch("visibilitychange");
    interrupted.frame();
  }
  interrupted.advance(1300);
  assert.deepEqual(interrupted.calls.vibrations, [], `${interruption} cancels the hold`);
  assert.equal(interrupted.zone.captures.size, 0, `${interruption} releases pointer capture`);
}

const gates = client();
for (const tab of ["chat", "reminders", "profile"]) {
  gates.view(tab);
  assert(gates.zone.hidden && gates.recenter.hidden);
  gates.pointer("pointerdown");
  gates.advance(1300);
  gates.pointer("pointerup");
}
assert.deepEqual(gates.calls.vibrations, []);
gates.view("chat", true);
assert(!gates.zone.hidden && !gates.recenter.hidden, "the fullscreen scene keeps touch framing available");
gates.model("classic");
assert(gates.zone.hidden && gates.recenter.hidden, "the classic model is excluded even in fullscreen");
console.log("Avatar touch interactions: r21 scene gate, pinch, haptic hold, release, recenter and cancellations PASS");
