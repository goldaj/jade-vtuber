/* DEV-010: dependency-free browser-lifecycle and geometry regression tests. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const web = path.join(__dirname, "../src/jade_runtime/mobile_web");
const script = fs.readFileSync(path.join(web, "room-motion.js"), "utf8");
const html = fs.readFileSync(path.join(web, "index.html"), "utf8");
const css = fs.readFileSync(path.join(web, "styles.css"), "utf8");

function element(initial = "") {
  const attributes = new Set();
  const style = { transform: "", opacity: "" };
  return {
    hidden: true, src: initial, style,
    getAttribute(name) { return name === "src" ? initial : null; },
    toggleAttribute(name, value) {
      if (value) attributes.add(name);
      else attributes.delete(name);
    },
    hasAttribute(name) { return attributes.has(name); },
  };
}

async function boot({ failure = false, supported = true } = {}) {
  const backdrop = element("/assets/room-spring.webp");
  const curtain = element();
  const left = element();
  const right = element();
  const steam = element();
  const reflection = element();
  const nodes = new Map([
    [".room-plane > img", backdrop],
    [".room-curtain", curtain],
    [".room-shadow-left", left],
    [".room-shadow-right", right],
    [".room-steam", steam],
    [".room-reflection", reflection],
  ]);
  const scene = {
    querySelector(q) { return nodes.get(q); },
    ...element(),
  };
  const handlers = new Map();
  const state = { hidden: false, reduced: false, intersecting: true };
  const media = {
    get matches() { return state.reduced; },
    addEventListener(type, fn) { handlers.set("media:" + type, fn); },
  };
  let observer;
  let nextId = 0;
  const frames = new Map();
  let paintCount = 0;
  let cancelled = 0;
  const clock = {
    step(time) {
      const jobs = [...frames.values()];
      frames.clear();
      for (const fn of jobs) {
        paintCount += 1;
        fn(time);
      }
    },
    get paintCount() { return paintCount; },
    get pending() { return frames.size; },
    get cancelled() { return cancelled; },
  };
  class FakeImage {
    set src(value) { this._src = value; }
    get src() { return this._src; }
    async decode() {
      if (failure && /room-curtain/.test(this.src)) throw Error("missing");
    }
    get naturalWidth() { return 100; }
    get naturalHeight() { return 100; }
  }
  const doc = {
    querySelector(q) { return q === ".room-art" ? scene : null; },
    get hidden() { return state.hidden; },
    addEventListener(type, fn) { handlers.set(type, fn); },
  };
  vm.runInNewContext(script, {
    document: doc, CSS: { supports: () => supported },
    Image: FakeImage,
    matchMedia: () => media,
    requestAnimationFrame(fn) { const id = ++nextId; frames.set(id, fn); return id; },
    cancelAnimationFrame(id) { cancelled++; frames.delete(id); },
    IntersectionObserver: class {
      constructor(fn) { observer = fn; }
      observe() {}
    },
    Math, Promise, Error,
  });
  // Flush the async Image.decode -> Promise.all -> then/catch chain.
  for (let i = 0; i < 10; i++) await Promise.resolve();
  return {
    backdrop, curtain, left, right, steam, reflection,
    scene, state, handlers, clock,
    intersection(value) { observer?.([{ isIntersecting: value }]); },
  };
}

(async () => {
  assert.match(html, /class="room-shadow room-shadow-left"/);
  assert.match(html, /class="room-shadow room-shadow-right"/);
  assert.match(html, /class="room-curtain"/);
  assert.match(html, /class="wisp wisp-four"/);
  assert.match(css, /prefers-reduced-motion:reduce/);
  assert.doesNotMatch(script, /drawImage|setInterval|fetch\(/);

  const r = await boot();
  assert.equal(r.backdrop.src, "/assets/room-backdrop.webp");
  assert.equal(r.curtain.hidden, false);
  assert.equal(r.left.hidden, false);
  assert.equal(r.right.hidden, false);
  assert.equal(r.steam.hidden, false);
  assert.ok(r.clock.pending > 0);

  let leftMin = Infinity, leftMax = -Infinity;
  let curtainMin = Infinity, curtainMax = -Infinity;
  let framesWithTransform = 0;
  for (let t = 0; t < 90_000; t += 16) {
    r.clock.step(t);
    const c = /rotate\(([-0-9.]+)deg\)/.exec(r.curtain.style.transform);
    const l = /translate3d\(([-0-9.]+)%/.exec(r.left.style.transform);
    if (c && l) {
      const cc = Number(c[1]);
      const ll = Number(l[1]);
      curtainMin = Math.min(curtainMin, cc);
      curtainMax = Math.max(curtainMax, cc);
      leftMin = Math.min(leftMin, ll);
      leftMax = Math.max(leftMax, ll);
      framesWithTransform++;
      assert.ok(Math.abs(cc) <= 9, "curtain rotation bounded to keep rings attached");
      assert.ok(Math.abs(ll) <= 11.5, "shadow displacement bounded");
    }
  }
  assert.ok(framesWithTransform > 1000);
  assert.ok(curtainMax - curtainMin > 6, "curtain amplitude perceivable");
  assert.ok(leftMax - leftMin > 8, "tree-shadow amplitude perceivable");

  r.state.hidden = true;
  r.handlers.get("visibilitychange")();
  assert.equal(r.clock.pending, 0);
  assert.equal(r.curtain.style.transform, "");
  assert.equal(r.scene.hasAttribute("data-paused"), true);
  r.state.hidden = false;
  r.handlers.get("visibilitychange")();
  assert.ok(r.clock.pending > 0);

  r.state.reduced = true;
  r.handlers.get("media:change")();
  assert.equal(r.clock.pending, 0);
  assert.equal(r.backdrop.src, "/assets/room-spring.webp");
  assert.equal(r.curtain.hidden, true);
  assert.equal(r.left.hidden, true);
  assert.equal(r.steam.hidden, true);

  r.state.reduced = false;
  r.handlers.get("media:change")();
  assert.equal(r.backdrop.src, "/assets/room-backdrop.webp");
  assert.equal(r.curtain.hidden, false);
  r.intersection(false);
  assert.equal(r.clock.pending, 0);
  r.intersection(true);
  assert.ok(r.clock.pending > 0);

  const failed = await boot({ failure: true });
  assert.equal(failed.backdrop.src, "/assets/room-spring.webp");
  assert.equal(failed.clock.pending, 0);
  assert.equal(failed.curtain.hidden, true);
  assert.equal(failed.steam.hidden, true);
  const oldBrowser = await boot({ supported: false });
  assert.equal(oldBrowser.backdrop.src, "/assets/room-spring.webp");
  assert.equal(oldBrowser.clock.pending, 0);
  console.log("DEV-010 room motion: amplitude, lifecycles, reduced-motion and fallback PASS");
})().catch(err => { console.error(err); process.exitCode = 1; });
