/* Geometry of the real resize path, with PIXI-compatible scaled dimensions. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../src/jade_runtime/mobile_web/avatar.js"), "utf8");

function point(x = 0, y = x) {
  return {x, y, set(nextX, nextY = nextX) { this.x = nextX; this.y = nextY; }};
}

class DisplayObject {
  constructor(width, height) {
    this.naturalWidth = width; this.naturalHeight = height;
    this.scale = point(1); this.position = point(); this.anchor = point();
    this.visible = true;
  }
  get width() { return this.naturalWidth * Math.abs(this.scale.x); }
  set width(value) { this.scale.x = value / this.naturalWidth; }
  get height() { return this.naturalHeight * Math.abs(this.scale.y); }
  set height(value) { this.scale.y = value / this.naturalHeight; }
  _render() {}
  updateTransform() {}
}

function snapshot(object) {
  return {x:object.position.x, y:object.position.y, width:object.width, height:object.height,
    scaleX:object.scale.x, scaleY:object.scale.y};
}

function close(actual, expected, message) {
  assert(Math.abs(actual - expected) <= 1e-9 * Math.max(1, Math.abs(expected)),
    `${message}: expected ${expected}, got ${actual}`);
}

function sameGeometry(actual, expected, message) {
  for (const name of Object.keys(expected)) close(actual[name], expected[name], `${message} (${name})`);
}

async function client() {
  const target = {clientWidth:390, clientHeight:650, isConnected:true,
    appendChild(){}, getClientRects(){return [{}];}};
  const shell = {dataset:{view:"home"}, immersive:false,
    classList:{contains(name){return name === "is-room-only" && shell.immersive;}}};
  const room = {dataset:{room:"kitchen", seatedReady:"false", seatedCompositor:"false"},
    addEventListener(){}, dispatchEvent(){}};
  const fallback = {classList:{add(){},remove(){}}}, status = {textContent:""}, mood = {textContent:""};
  const document = {
    hidden:false, addEventListener(){},
    querySelector(selector){return {".shell":shell, ".room":room}[selector] || null;},
    getElementById(id){return {"avatar-container":target, "avatar-fallback":fallback,
      "avatar-state":status, "mood-line":mood}[id];}
  };
  // A standing model with a portrait aspect ratio; dimensions always reflect
  // scale, as PIXI does. Fixed width/height mocks would hide resize drift.
  const model = new DisplayObject(600, 1300);
  model.internalModel = {coreModel:{getDrawableRenderOrders(){return [0];}}, draw(){}};
  model.motion = () => Promise.resolve();
  const sprites = [], isolationStates = [], viewport = {};
  class Container {
    constructor(){this.children = [];}
    addChild(child){this.children.push(child); child.parent = this;}
    addChildAt(child, index){this.children.splice(index, 0, child); child.parent = this;}
  }
  class Application {
    constructor() {
      this.view = {}; this.stage = new Container();
      this.renderer = {resize(width, height){viewport.width = width; viewport.height = height;}};
      this.ticker = {start(){},stop(){},add(){}};
    }
  }
  const PIXI = {
    Application, Container,
    Sprite:{from(image){
      const sprite = new DisplayObject(image.naturalWidth, image.naturalHeight);
      sprite.texture = {}; sprites.push(sprite); return sprite;
    }},
    live2d:{Live2DModel:{async from(){return model;}}}
  };
  const profile = {id:"classic", available:true, manifestUrl:"/model/Jade.model3.json",
    presentation:"seated", classicIntents:true, idleMotion:"Idle"};
  const window = {PIXI, Live2DCubismCore:{}, devicePixelRatio:1,
    JadeModelCatalog:{defaultId:"classic", ready:Promise.resolve([profile]),
      get(id){return id === profile.id ? profile : null;}, list(){return [profile];}},
    JadeAvatarModelLoader:{async load(selected){
      assert.equal(selected.id, "classic"); return {model, dispose(){model.autoUpdate = false;}};
    }},
    JadeHeadIsolation:{forModel(){return {canLayerHair:true,
      sync(active){isolationStates.push(active);}, drawPass(_name, draw){return draw();}};}}};
  vm.runInNewContext(source, {window, document, console,
    fetch:async()=>({ok:true,json:async()=>({version:1,enabled:false,intents:{}})}),
    ResizeObserver:class {observe(){}},
    setTimeout, clearTimeout
  }, {filename:"avatar.js"});
  for (let turn = 0; turn < 60; turn++) await Promise.resolve();
  assert.equal(window.JadeAvatar.ready, true, status.textContent);
  function resize(width, height, view = shell.dataset.view, immersive = false) {
    target.clientWidth = width; target.clientHeight = height;
    shell.dataset.view = view; shell.immersive = immersive;
    window.JadeAvatar.resize();
    assert.equal(viewport.width, width); assert.equal(viewport.height, height);
    return snapshot(model);
  }
  return {window, model, room, shell, target, sprites, isolationStates, resize};
}

(async () => {
  const a = await client();
  const sizes = [[336,180], [388,220], [360,115], [780,150], [300,500], [520,650]];
  for (const view of ["chat", "reminders", "profile"]) {
    for (const [width, height] of sizes) {
      a.room.dataset.room = "kitchen";
      const geometry = a.resize(width, height, view);
      const top = geometry.y - a.model.anchor.y * geometry.height;
      const left = geometry.x - a.model.anchor.x * geometry.width;
      const right = left + geometry.width;
      assert(top > 0, `${view} ${width}x${height}: leave room above the head`);
      assert(top < height / 4, "the head stays near the top, not the vertical centre");
      assert(top + geometry.height / 2 <= height, "the upper half remains visible in a short scene");
      assert(left >= 0 && right <= width, "the head must not be cropped horizontally");
      close(geometry.x, width / 2, "the model stays horizontally centred");
      close(geometry.scaleX, geometry.scaleY, "uniform model scale");
      close(geometry.width / geometry.height, a.model.naturalWidth / a.model.naturalHeight,
        "the original model proportions are preserved");
      for (let count = 0; count < 10; count++)
        sameGeometry(a.resize(width, height, view), geometry, "repeated resize must not drift");
      a.room.dataset.room = "bedroom";
      sameGeometry(a.resize(width, height, view), geometry, "missing seated artwork uses the same face-priority framing");
    }
  }
  const short = a.resize(780, 150, "chat");
  assert(short.y + (1 - a.model.anchor.y) * short.height > a.target.clientHeight,
    "short scenes may crop the lower body to retain a readable head");

  // Home and immersive transforms must be recovered after arbitrary visits,
  // dimensions and rooms, rather than accumulating the mini-scene camera.
  a.room.dataset.room = "kitchen";
  const home = a.resize(390, 650, "home");
  const fullscreen = a.resize(390, 844, "home", true);
  for (const view of ["chat", "reminders", "profile"]) {
    a.resize(780, 150, view);
    sameGeometry(a.resize(390, 844, view, true), fullscreen, "fullscreen ignores the originating menu");
    a.resize(336, 180, view);
    sameGeometry(a.resize(390, 650, "home"), home, "home camera is restored on return");
  }

  // The seated head and body keep one registration. The CSS camera moves the
  // common scene plane; entering a menu must not reposition the head alone.
  a.room.dataset.room = "bedroom";
  a.room.dataset.seatedReady = "true";
  a.room.dataset.seatedCompositor = "true";
  assert.equal(a.window.JadeAvatar.prepareSeatedComposition({naturalWidth:670, naturalHeight:956}), true);
  const body = a.sprites[0];
  const seatedHead = a.resize(470.5, 836, "home");
  const seatedBody = snapshot(body);
  assert.equal(body.visible, true);
  for (const view of ["chat", "reminders", "profile", "home"]) {
    for (const immersive of [false, true]) {
      sameGeometry(a.resize(470.5, 836, view, immersive), seatedHead, "seated head registration is menu-independent");
      sameGeometry(snapshot(body), seatedBody, "seated body registration is menu-independent");
      assert.equal(a.isolationStates.at(-1), true, "seated head isolation stays active");
    }
  }
  for (const factor of [0.6, 1.25, 2, 1]) {
    const head = a.resize(470.5 * factor, 836 * factor, "chat");
    const torso = snapshot(body);
    for (const key of Object.keys(head)) {
      close(head[key] / factor, seatedHead[key], `head scales with its scene (${key})`);
      close(torso[key] / factor, seatedBody[key], `body scales with the same scene (${key})`);
    }
  }
  sameGeometry(a.resize(470.5, 836, "home"), seatedHead, "seated home camera is restored");
  console.log("Scene framing: face priority, portrait/landscape, stable resize and shared seated registration PASS");
})().catch(error => {console.error(error); process.exitCode = 1;});
