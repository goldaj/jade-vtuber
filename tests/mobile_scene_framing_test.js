/* r21 portrait geometry through the real resize path and PIXI-scaled dimensions. */
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
  const room = {dataset:{room:"kitchen"},
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
  const model = new DisplayObject(3840, 5000);
  model.internalModel = {coreModel:{getDrawableRenderOrders(){return [0];}}, draw(){}};
  model.motion = () => Promise.resolve();
  const viewport = {};
  class Container extends DisplayObject {
    constructor(){super(0,0);this.children = [];}
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
  const PIXI = {Application, Container, live2d:{}};
  const profile = {id:"next", available:true, manifestUrl:"/models/next/Jade.model3.json",
    presentation:"full", classicIntents:false, idleMotion:"Idle"};
  const window = {PIXI, Live2DCubismCore:{}, devicePixelRatio:1,
    JadeModelCatalog:{defaultId:"next", ready:Promise.resolve([profile]),
      get(id){return id === profile.id ? profile : null;}, list(){return [profile];}},
    JadeAvatarModelLoader:{async load(selected){
      assert.equal(selected.id, "next", "only r21 belongs to this campaign");
      return {model, dispose(){model.autoUpdate = false;}};
    }}};
  vm.runInNewContext(source, {window, document, console,
    fetch:async()=>({ok:true,json:async()=>({version:1,enabled:false,intents:{}})}),
    ResizeObserver:class {observe(){}},
    setTimeout, clearTimeout
  }, {filename:"avatar.js"});
  for (let turn = 0; turn < 60; turn++) await Promise.resolve();
  assert.equal(window.JadeAvatar.ready, true, status.textContent);
  function resize(width, height, view = shell.dataset.view, immersive = false, extraCanvasHeight = 0) {
    target.clientWidth = width; target.clientHeight = height + extraCanvasHeight;
    target.parentElement = {clientHeight:height};
    shell.dataset.view = view; shell.immersive = immersive;
    window.JadeAvatar.resize();
    assert.equal(viewport.width, width); assert.equal(viewport.height, height + extraCanvasHeight);
    return snapshot(model);
  }
  return {window, model, room, shell, target, resize};
}

(async () => {
  const a = await client();
  // Absolute eye centres and spacing recorded for the current r21 portrait
  // camera. No other model or renderer participates in these expectations.
  const cases = [
    [336,180,[173.48625,15.35175,27.10125]],
    [388,220,[199.45875,18.76325,33.12375]],
    [360,115,[191.05,6.71,18.25]],
    [780,150,[422.071875,12.793125,22.584375]],
    [300,500,[149.61523438,175.35039062,35.21679688]],
    [520,650,[259.33307292,177.40734375,61.04244792]],
    [413,735,[205.97030599,268.65237109,48.48179036]],
    [400,220,[206.11875,18.76325,33.12375]],
    [845,223,[452.8771875,19.0191125,33.5754375]],
    [390,650,[194.49980469,227.95550781,45.78183594]],
    [390,844,[194.49980469,341.25150781,45.78183594]],
    [941,1672,[469.29311849,610.55705859,110.46335286]],
  ];
  const eyes = geometry => [geometry.x, geometry.y + (761 - 2500) * geometry.scaleY, 289 * geometry.scaleX];
  for (const room of ["bedroom", "kitchen", "living"]) {
    a.room.dataset.room = room;
    for (const view of ["home", "chat", "reminders", "profile"]) {
      for (const [width, height, expectedEyes] of cases) {
        const geometry = a.resize(width, height, view);
        const actualEyes = eyes(geometry);
        actualEyes.forEach((value,index) => close(value,expectedEyes[index],
          `${room} ${view} ${width}x${height}: r21 eye registration (${index})`));
        assert(actualEyes[0] - actualEyes[2] / 2 > 0 && actualEyes[0] + actualEyes[2] / 2 < width,
          "both eyes remain horizontally visible");
        assert(actualEyes[1] > 0 && actualEyes[1] < height,"the face stays within the portrait frame");
        close(geometry.scaleX,geometry.scaleY,"uniform r21 model scale");
        close(geometry.width / geometry.height,3840 / 5000,"r21 proportions remain intact");
        for (let count = 0; count < 5; count++)
          sameGeometry(a.resize(width,height,view),geometry,"repeated resize does not drift");
        sameGeometry(a.resize(width,height,view,false,88),geometry,
          "extending the render surface below the portrait must not move its camera");
      }
    }
  }

  // Menu visits and fullscreen entry must restore the same r21 registration.
  const home = a.resize(390,650,"home");
  const fullscreen = a.resize(390,844,"home",true);
  for (const room of ["bedroom", "kitchen", "living"]) {
    a.room.dataset.room = room;
    for (const view of ["chat", "reminders", "profile"]) {
      a.resize(780,150,view);
      sameGeometry(a.resize(390,844,view,true),fullscreen,"fullscreen ignores the originating menu");
      a.resize(336,180,view);
      sameGeometry(a.resize(390,650,"home"),home,"the home camera is restored after a menu visit");
    }
  }

  const reference = a.resize(941,1672,"home");
  for (const factor of [.6,1.25,2,1]) {
    const geometry = a.resize(941 * factor,1672 * factor,"chat");
    for (const key of Object.keys(reference))
      close(geometry[key] / factor,reference[key],`r21 follows the portrait plane (${key})`);
  }
  sameGeometry(a.resize(941,1672,"home"),reference,"the initial portrait transform is recovered");
  console.log("r21 framing: 3 rooms, 4 views, 12 sizes, absolute eye landmarks, fullscreen and stable resize PASS");
})().catch(error => {console.error(error); process.exitCode = 1;});
