/* Execute the actual client: scene gestures share the button's fullscreen path. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const {webcrypto} = require("node:crypto");
const source = fs.readFileSync(path.join(__dirname, "../src/jade_runtime/mobile_web/app.js"), "utf8");

class Element {
  constructor(tag = "div") {
    this.tagName = tag.toUpperCase();
    this.dataset = {}; this.attributes = {}; this.listeners = {};
    this.children = []; this.parentElement = null; this.disabled = false;
    const classes = new Set();
    this.classList = {
      add(...names) { names.forEach(name => classes.add(name)); },
      remove(...names) { names.forEach(name => classes.delete(name)); },
      contains(name) { return classes.has(name); },
      toggle(name, force = !classes.has(name)) {
        if (force) classes.add(name); else classes.delete(name);
        return force;
      }
    };
    this.properties = {};
    this.style = {
      setProperty:(name, value) => { this.properties[name] = value; },
      removeProperty:name => { delete this.properties[name]; }
    };
  }
  addEventListener(type, listener, options) {
    (this.listeners[type] ||= []).push({listener, capture:options === true || options?.capture});
  }
  setAttribute(name, value) { this.attributes[name] = value; }
  removeAttribute(name) { delete this.attributes[name]; }
  appendChild(child) {
    if (child.parentElement) child.parentElement.children = child.parentElement.children.filter(x => x !== child);
    this.children.push(child); child.parentElement = this;
    return child;
  }
  insertBefore(child) { return this.appendChild(child); }
  contains(target) {
    for (let element = target; element; element = element.parentElement) if (element === this) return true;
    return false;
  }
  closest(selector) {
    const matches = element => selector.split(",").some(part => {
      if (part.startsWith(".")) return element.classList.contains(part.slice(1));
      if (part === "[role='button']") return element.attributes.role === "button";
      if (part === "[contenteditable]") return "contenteditable" in element.attributes;
      return element.tagName.toLowerCase() === part;
    });
    for (let element = this; element; element = element.parentElement) if (matches(element)) return element;
    return null;
  }
  querySelector() { return this.children[0] || new Element("button"); }
  getBoundingClientRect() { return {width:480, height:240}; }
}

function client(mode = "css") {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, new Element());
    return elements.get(id);
  };
  const document = new Element(), window = new Element();
  const shell = new Element("main"), room = new Element("section"), dock = new Element();
  const plane = new Element(), picture = new Element("img"), picker = new Element();
  picker.classList.add("room-picker");
  const selector = element("room-selector"); selector.tagName = "SELECT";
  picker.appendChild(selector);
  shell.dataset.view = "home";
  document.appendChild(shell); shell.appendChild(room);
  room.appendChild(plane); plane.appendChild(picture); room.appendChild(picker); room.appendChild(dock);
  const mic = element("mic"); mic.tagName = "BUTTON"; dock.appendChild(mic);
  const form = element("composer"), input = element("message");
  form.appendChild(input); shell.appendChild(form);
  const button = element("fullscreen"); button.tagName = "BUTTON"; shell.appendChild(button);
  const nav = ["home", "chat", "reminders", "profile"].map(view => {
    const item = new Element("button"); item.dataset.viewTarget = view; shell.appendChild(item); return item;
  });
  document.querySelector = selector => ({".shell":shell, ".room":room, ".room-plane":plane, ".room-bottom":dock})[selector] || null;
  document.querySelectorAll = selector => selector === ".app-nav-item" ? nav : [];
  document.getElementById = element;
  document.hidden = false; document.fullscreenElement = null;
  window.location = {hash:""}; window.crypto = webcrypto;
  let resizeCount = 0, requestCount = 0, exitCount = 0, finishRequest;
  window.JadeAvatar = {
    resize(){resizeCount++;}, setMouth(){}, setSpeaking(){}, resetIntent(){}
  };
  const documentEvent = type => (document.listeners[type] || []).forEach(({listener}) => listener({type}));
  if (mode !== "css") shell.requestFullscreen = async () => {
    requestCount++;
    if (mode === "reject") throw new Error("Fullscreen unavailable");
    if (mode === "pending") await new Promise(resolve => { finishRequest = resolve; });
    document.fullscreenElement = shell; documentEvent("fullscreenchange");
  };
  document.exitFullscreen = async () => {
    exitCount++; document.fullscreenElement = null; documentEvent("fullscreenchange");
  };
  vm.runInNewContext(source, {document, window, navigator:{}, crypto:webcrypto,
    setInterval(){return 1;}, clearInterval(){}, console,
    fetch(){throw new Error("Scene gestures must not make network requests");}
  }, {filename:"app.js"});

  async function emit(target, type, values = {}) {
    const event = {type, target, button:0, timeStamp:1000, defaultPrevented:false,
      preventDefault(){this.defaultPrevented = true;}, ...values};
    const pending = [];
    for (const {listener, capture} of document.listeners[type] || []) if (capture) pending.push(listener(event));
    for (let current = target; current; current = current.parentElement) {
      event.currentTarget = current;
      for (const {listener, capture} of current.listeners[type] || []) if (!capture) pending.push(listener(event));
    }
    await Promise.all(pending);
    await Promise.resolve();
    return event;
  }
  const pointer = (type, time, options = {}) => emit(options.target || picture, type, {
    pointerType:"touch", pointerId:1, isPrimary:true, clientX:120, clientY:90, timeStamp:time, ...options
  });
  async function tap(time, options = {}) {
    await pointer("pointerdown", time, options);
    return pointer("pointerup", time + 40, options);
  }
  return {shell, room, picture, picker, selector, mic, form, dock, button, document, window, emit, pointer, tap,
    async view(view) { await emit(nav.find(item => item.dataset.viewTarget === view), "click"); },
    get fullscreen() { return shell.classList.contains("is-room-only"); },
    get resizeCount() { return resizeCount; },
    get requestCount() { return requestCount; }, get exitCount() { return exitCount; },
    async finishRequest() { finishRequest(); await Promise.resolve(); await Promise.resolve(); },
    escape() { document.fullscreenElement = null; documentEvent("fullscreenchange"); }
  };
}

(async () => {
  for (const view of ["home", "chat", "reminders", "profile"]) {
    const a = client();
    await a.view(view);
    assert(a.resizeCount > 0, "navigation recalculates the camera even if dimensions are unchanged");
    a.mic.disabled = true; a.mic.classList.add("recording");
    await a.emit(a.picture, "click");
    assert.equal(a.fullscreen, false, "one click has no effect");
    const opened = await a.emit(a.picture, "dblclick");
    assert.equal(opened.defaultPrevented, true);
    assert.equal(a.fullscreen, true, `${view}: mouse opens fullscreen`);
    assert.equal(a.mic.parentElement, a.dock);
    assert.equal(a.mic.disabled, true);
    assert.equal(a.mic.classList.contains("recording"), true);
    assert.equal(a.button.attributes["aria-pressed"], "true");
    assert.equal(a.shell.properties["--room-immersive-width"], "480px");
    await a.emit(a.picture, "dblclick", {timeStamp:1300});
    assert.equal(a.fullscreen, false, `${view}: mouse returns to the previous view`);
    assert.equal(a.shell.dataset.view, view);
    assert.equal(a.mic.parentElement, view === "home" ? a.dock : a.form);
    assert.equal(a.button.attributes["aria-pressed"], "false");
    assert.equal(a.shell.properties["--room-immersive-width"], undefined);

    const b = client(); await b.view(view);
    await b.tap(10); assert.equal(b.fullscreen, false, "one tap has no effect");
    await b.tap(180); assert.equal(b.fullscreen, true, `${view}: two touch taps open fullscreen`);
    await b.emit(b.picture, "dblclick", {timeStamp:230});
    assert.equal(b.fullscreen, true, "compatibility dblclick must not undo the touch toggle");
    await b.tap(400); await b.tap(580);
    assert.equal(b.fullscreen, false, `${view}: two touch taps leave fullscreen`);
    assert.equal(b.shell.dataset.view, view);
  }

  for (const control of ["mic", "selector", "picker"]) {
    const a = client();
    const child = new Element("span"); a[control].appendChild(child);
    const ignored = await a.emit(child, "dblclick");
    assert.equal(ignored.defaultPrevented, false, `${control}: control action stays available`);
    await a.tap(100, {target:child}); await a.tap(250, {target:child});
    assert.equal(a.fullscreen, false, `${control}: nested control is excluded`);
  }
  for (const tag of ["a", "input", "textarea", "label", "summary"]) {
    const a = client(), control = new Element(tag); a.room.appendChild(control);
    await a.emit(control, "dblclick");
    assert.equal(a.fullscreen, false, `${tag}: interactive content is excluded`);
  }
  const wrongButton = client();
  await wrongButton.emit(wrongButton.picture, "dblclick", {button:2});
  assert.equal(wrongButton.fullscreen, false);

  const slow = client(); await slow.tap(0); await slow.tap(500);
  assert.equal(slow.fullscreen, false, "separated taps are not a double tap");
  const distant = client(); await distant.tap(0); await distant.tap(180, {clientX:200});
  assert.equal(distant.fullscreen, false, "distant taps are not a double tap");
  const drag = client(); await drag.tap(0);
  await drag.pointer("pointerdown", 180);
  await drag.pointer("pointermove", 200, {clientY:130});
  await drag.pointer("pointerup", 230);
  assert.equal(drag.fullscreen, false, "a drag returning to its origin is rejected");
  const held = client(); await held.tap(0);
  await held.pointer("pointerdown", 180); await held.pointer("pointerup", 700);
  assert.equal(held.fullscreen, false, "long presses are rejected");
  const cancelled = client(); await cancelled.tap(0);
  await cancelled.pointer("pointerdown", 180); await cancelled.pointer("pointercancel", 190);
  await cancelled.pointer("pointerup", 200); await cancelled.tap(260);
  assert.equal(cancelled.fullscreen, false, "cancelled gestures clear the earlier tap");
  for (const outside of [false, true]) {
    const a = client(); await a.tap(0); await a.pointer("pointerdown", 180);
    const second = {pointerId:2, isPrimary:false, target:outside ? a.form : a.picture};
    await a.pointer("pointerdown", 190, second);
    await a.pointer("pointerup", 200, second); await a.pointer("pointerup", 210);
    await a.tap(260);
    assert.equal(a.fullscreen, false, "a second finger cancels even when it lands outside the scene");
  }
  const scrolling = client(); await scrolling.tap(0);
  await scrolling.emit(scrolling.form, "scroll"); await scrolling.tap(180);
  assert.equal(scrolling.fullscreen, false, "scroll cancels the earlier tap");
  const navigated = client(); await navigated.tap(0); await navigated.view("chat"); await navigated.tap(180);
  assert.equal(navigated.fullscreen, false, "a tap cannot carry over between views");

  const native = client("native"); await native.view("chat");
  await native.emit(native.button, "click");
  assert.equal(native.requestCount, 1); assert.equal(native.fullscreen, true);
  await native.emit(native.picture, "dblclick");
  assert.equal(native.exitCount, 1); assert.equal(native.fullscreen, false);
  await native.tap(2000); await native.tap(2180);
  assert.equal(native.requestCount, 2); native.escape();
  assert.equal(native.fullscreen, false, "browser escape leaves immersive mode");
  assert.equal(native.shell.dataset.view, "chat");
  assert.equal(native.mic.parentElement, native.form);

  const rejected = client("reject"); await rejected.tap(0); await rejected.tap(180);
  assert.equal(rejected.fullscreen, true, "denied native fullscreen retains the CSS fallback");
  await rejected.emit(rejected.button, "click");
  assert.equal(rejected.fullscreen, false); assert.equal(rejected.exitCount, 0);

  const pending = client("pending");
  await pending.emit(pending.picture, "dblclick");
  await pending.emit(pending.picture, "dblclick", {timeStamp:1400});
  assert.equal(pending.requestCount, 1, "overlapping native requests are coalesced");
  await pending.finishRequest();
  await pending.emit(pending.picture, "dblclick", {timeStamp:1800});
  assert.equal(pending.exitCount, 1); assert.equal(pending.fullscreen, false);
  const pendingTouch = client("pending");
  await pendingTouch.emit(pendingTouch.picture, "dblclick");
  await pendingTouch.tap(1100); await pendingTouch.tap(1280);
  await pendingTouch.finishRequest(); await pendingTouch.tap(1430);
  assert.equal(pendingTouch.fullscreen, true, "ignored taps during native transition cannot combine with the next tap");
  console.log("Scene fullscreen gestures: all menus, mouse/touch, native/fallback, control/drag/pinch isolation PASS");
})().catch(error => { console.error(error); process.exitCode = 1; });
