/* Selection owns one model lifetime, including late loads and fallback. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const web = path.join(__dirname, "../src/jade_runtime/mobile_web");
const source = fs.readFileSync(path.join(web, "avatar.js"), "utf8");
const seatedSource = fs.readFileSync(path.join(web, "seated-scene.js"), "utf8");
const visualPalette = JSON.parse(fs.readFileSync(path.join(web, "intent-visuals.json"), "utf8"));

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return {promise, resolve, reject};
}
async function flush() { for (let n = 0; n < 60; n++) await Promise.resolve(); }
function point(x = 0, y = x) {
  return {x, y, set(nextX, nextY = nextX) { this.x = nextX; this.y = nextY; }};
}
class Element {
  constructor() {
    this.listeners = {}; this.children = []; this.dataset = {}; this.attributes = {};
    this.hidden = false; this.isConnected = true; this.textContent = "";
    const classes = new Set();
    this.classList = {add(...names){names.forEach(name => classes.add(name));},
      remove(...names){names.forEach(name => classes.delete(name));}, contains(name){return classes.has(name);},
      toggle(name, force = !classes.has(name)){if (force) classes.add(name); else classes.delete(name); return force;}};
    this.style = {setProperty(){},removeProperty(){}};
  }
  addEventListener(name, callback) { (this.listeners[name] ||= []).push(callback); }
  dispatchEvent(event) { for (const callback of this.listeners[event.type] || []) callback(event); return true; }
  setAttribute(name, value) { this.attributes[name] = value; }
  removeAttribute(name) { delete this.attributes[name]; if (name === "src") this.src = ""; }
  appendChild(child) { if (child.parentElement) child.parentElement.removeChild(child); this.children.push(child); child.parentElement = this; return child; }
  removeChild(child) { this.children = this.children.filter(item => item !== child); child.parentElement = null; }
  remove() { this.parentElement?.removeChild(this); }
  getClientRects() { return this.isConnected ? [{}] : []; }
}
class DisplayObject {
  constructor(width = 600, height = 1300) {
    this.naturalWidth = width; this.naturalHeight = height;
    this.scale = point(1); this.position = point(); this.anchor = point();
    this.visible = true; this.destroyed = false;
  }
  get width() { return this.naturalWidth * Math.abs(this.scale.x); }
  set width(value) { this.scale.x = value / this.naturalWidth; }
  get height() { return this.naturalHeight * Math.abs(this.scale.y); }
  set height(value) { this.scale.y = value / this.naturalHeight; }
  _render() {}
  updateTransform() {}
  destroy() { this.destroyed = true; this.parent?.removeChild(this); }
}
class Container extends DisplayObject {
  constructor() { super(); this.children = []; }
  addChild(child) { return this.addChildAt(child, this.children.length); }
  addChildAt(child, index) { child.parent?.removeChild(child); this.children.splice(index, 0, child); child.parent = this; return child; }
  removeChild(child) { this.children = this.children.filter(item => item !== child); child.parent = null; return child; }
  removeChildren() { const children = this.children.slice(); children.forEach(child => this.removeChild(child)); return children; }
  destroy(options) { if (options?.children) this.children.slice().forEach(child => child.destroy?.(options)); super.destroy(); }
}

async function client({hidden = false, initialError = false, delayBodyImage = false, failCompositionMount = false,
    defaultId = "classic", reactions = false} = {}) {
  const target = new Element(); target.clientWidth = 390; target.clientHeight = 690;
  const room = new Element(); room.dataset = {room:"bedroom",seatedReady:"false",seatedCompositor:"false"};
  const shell = new Element(); shell.dataset.view = "profile";
  const fallback = new Element(), status = new Element(), mood = new Element();
  const body = new Element(), backdrop = new Element();
  const document = new Element(); document.hidden = hidden;
  document.querySelector = selector => ({".room":room,".shell":shell})[selector] || null;
  document.getElementById = id => ({"avatar-container":target,"avatar-fallback":fallback,"avatar-state":status,
    "mood-line":mood,"portrait-seated-body":body,"portrait-bedroom":backdrop})[id] || null;
  const profiles = [
    {id:"classic",label:"Actuel",available:true,manifestUrl:"/model/Jade.model3.json",presentation:"seated",classicIntents:true,idleMotion:"Idle"},
    {id:"next",label:"Nouveau modèle",available:true,manifestUrl:"/models/next/Jade.model3.json",presentation:"full",classicIntents:false,idleMotion:"Idle"},
    {id:"locked",label:"Indisponible",available:false,manifestUrl:null,presentation:"full",classicIntents:false,idleMotion:null}
  ];
  const plans = new Map(), active = new Set(), models = [], events = [], states = [], applications = [], sprites = [], waitingBodyImages = [];
  const compositionLayers = [], isolationSyncs = [];
  let pending = 0, maximum = 0, maximumPending = 0, visibleObserver;
  const timers = new Map();
  let timerSequence = 0;
  if (initialError) plans.set(defaultId, [Promise.reject(new Error("initial load failed"))]);
  // A rejected planned load is consumed by the test loader, not an unhandled rejection.
  for (const list of plans.values()) list.forEach(operation => operation.catch(() => {}));
  class Application {
    constructor() {
      this.view = new Element(); this.stage = new Container();
      const addChildAt = this.stage.addChildAt;
      this.stage.addChildAt = function(child, index) {
        if (failCompositionMount && child.texture) throw new Error("seated sprite could not be mounted");
        return addChildAt.call(this, child, index);
      };
      this.renderer = {resize(){}};
      this.ticker = {running:false,start(){this.running = true;},stop(){this.running = false;},add(callback){this.callback = callback;},remove(){}};
      applications.push(this);
    }
    destroy(removeView) { this.ticker.stop(); if (removeView) this.view.remove(); this.destroyed = true; }
  }
  class CompositionLayer extends Container {
    constructor() { super(); compositionLayers.push(this); }
  }
  const PIXI = {Application, Container:CompositionLayer, UPDATE_PRIORITY:{LOW:-50},
    Sprite:{from(image){const sprite = new DisplayObject(image.naturalWidth,image.naturalHeight);
      sprite.texture = {destroyed:false,baseTexture:{destroyed:false},destroy(baseTexture){
        this.destroyed = true; if (baseTexture) this.baseTexture.destroyed = true;
      }};
      sprite.destroy = options => {
        if (options?.texture) sprite.texture.destroy(options.baseTexture);
        DisplayObject.prototype.destroy.call(sprite);
      };
      sprites.push(sprite); return sprite;}},
    live2d:{Live2DModel:{from(){throw new Error("Use the owned model loader");},fromSync(){throw new Error("Use the owned model loader");}}}};
  const window = new Element(); Object.assign(window, {PIXI,Live2DCubismCore:{},devicePixelRatio:1,
    JadeModelCatalog:{defaultId,ready:Promise.resolve(profiles),list:()=>profiles,get:id=>profiles.find(profile=>profile.id===id)||null},
    JadeHeadIsolation:{forModel(){const calls = []; isolationSyncs.push(calls);
      return {canLayerHair:true,sync(value){calls.push(value);},drawPass(_name,draw){return draw();}};}}
  });
  window.JadeAvatarModelLoader = {async load(profile) {
    assert.equal(active.size, 0, "destroy the previous model before starting the next load");
    assert.equal(pending, 0, "never overlap model load operations");
    if (window.JadeAvatar) assert.equal(window.JadeAvatar.usesSeatedBody, false, "no static body belongs to an unready model");
    pending++; maximumPending = Math.max(maximumPending,pending);
    events.push(`load:${profile.id}`);
    const plan = plans.get(profile.id)?.shift();
    try { if (plan) await plan; }
    catch (error) { events.push(`failed:${profile.id}`); throw error; }
    finally { pending--; }
    const model = new DisplayObject(3840, profile.id === "next" ? 5000 : 4160);
    model.id = profile.id; model.autoUpdate = false;
    const {EventEmitter} = require("node:events");
    model.internalModel = Object.assign(new EventEmitter(), {
      coreModel:{getDrawableRenderOrders(){return [0];},setParameterValueById(id,value){model.lastParameter={id,value};}},
      draw(){},eyeBlink:{updateParameters(){model.blinked = true;}},
      motionManager:Object.assign(new EventEmitter(), {
        expressionManager:{defaultExpression:{}, resetExpression(){model.neutral = (model.neutral || 0) + 1;}},
      }),
    });
    model.motions = [];
    model.expressions = [];
    model.motion = (group, index, priority) => {
      model.motions.push({group,index,priority});
      if (group === "Idle") model.idle = (model.idle || 0) + 1;
      model.internalModel.motionManager.emit("motionLoaded", group, index, {
        setIsLoop(value){model.loops = value;},setIsLoopFadeIn(value){model.loopFade = value;},
      });
      return Promise.resolve();
    };
    model.expression = expression => { model.expressions.push(expression); return Promise.resolve(); };
    model.destroy = () => {
      if (model.destroyed) return;
      model.destroyed = true; model.autoUpdate = false; model.parent?.removeChild(model);
      active.delete(model); events.push(`dispose:${profile.id}`);
    };
    active.add(model); models.push(model); maximum = Math.max(maximum,active.size);
    events.push(`created:${profile.id}`);
    return {model,dispose:() => model.destroy()};
  }};
  room.addEventListener("jade-avatar-state", () => {
    states.push({...window.JadeAvatar.state});
  });
  class Event { constructor(type){this.type = type;} }
  class CustomEvent extends Event { constructor(type,options){super(type);this.detail=options?.detail;} }
  const context = {window,document,Event,CustomEvent,console:{warn(){},log(){},error(){}},
    fetch:async()=>({ok:true,json:async()=>({...visualPalette,enabled:reactions})}),
    Image:class {set src(value){this._src=value;const bodyImage=value.includes("seated-body");
      this.naturalWidth=bodyImage?670:864;this.naturalHeight=bodyImage?956:1536;
      if(bodyImage && delayBodyImage)waitingBodyImages.push(this);else Promise.resolve().then(()=>this.onload?.());}
      get src(){return this._src;}removeAttribute(name){if(name==="src")this._src="";}},
    ResizeObserver:class {observe(){} disconnect(){}},
    IntersectionObserver:class {constructor(callback){visibleObserver=callback;}observe(){}disconnect(){}},
    performance:{now(){return 10;}},
    setTimeout(callback, delay){const id = ++timerSequence; timers.set(id, {callback,delay}); return id;},
    clearTimeout(id){timers.delete(id);}};
  vm.createContext(context);
  vm.runInContext(seatedSource,context,{filename:"seated-scene.js"});
  vm.runInContext(source,context,{filename:"avatar.js"});
  await flush();
  return {avatar:window.JadeAvatar,window,room,shell,document,target,fallback,body,models,active,events,states,applications,sprites,compositionLayers,isolationSyncs,
    hold(id){const gate=deferred();(plans.get(id)||plans.set(id,[]).get(id)).push(gate.promise);return gate;},
    failNext(id){const gate=this.hold(id);gate.promise.catch(()=>{});gate.reject(new Error(`failed ${id}`));},
    hide(value){document.hidden=value;document.dispatchEvent(new Event("visibilitychange"));},
    visible(value){visibleObserver([{isIntersecting:value}]);},
    completeBodyImages(){waitingBodyImages.splice(0).forEach(image=>image.onload?.());},
    runTimers(delay){for (const [id, timer] of timers) if (timer.delay === delay) { timers.delete(id); timer.callback(); }},
    get maximum(){return maximum;},get maximumPending(){return maximumPending;},get pending(){return pending;}};
}

(async () => {
  const a = await client();
  assert.equal(a.avatar.state.status,"ready");
  assert.equal(a.avatar.state.modelId,"classic");
  assert.equal(a.avatar.usesSeatedBody,true);
  assert.equal(a.room.dataset.seatedReady,"true");
  assert.equal(a.models[0].idle,1);
  const initialEvents = a.events.slice(), first = a.models[0];
  assert.equal(await a.avatar.selectModel("classic"),true);
  assert.equal(await a.avatar.selectModel("locked"),false);
  assert.equal(await a.avatar.selectModel("unknown"),false);
  assert.deepEqual(a.events,initialEvents,"same and unavailable choices preserve the existing instance");
  assert.equal(first.destroyed,false);

  const nextGate = a.hold("next");
  const nextResult = a.avatar.selectModel("next");
  await flush();
  assert.equal(first.destroyed,true);
  assert.equal(a.active.size,0);
  assert.equal(a.avatar.state.status,"loading");
  assert.equal(a.avatar.state.requestedId,"next");
  assert.equal(a.avatar.usesSeatedBody,false);
  assert.equal(a.room.dataset.seatedReady,"false","old static body disappears while loading");
  nextGate.resolve(); assert.equal(await nextResult,true); await flush();
  assert.equal(a.avatar.state.modelId,"next");
  assert.equal(a.avatar.usesSeatedBody,false);
  assert.equal(a.room.dataset.seatedReady,"false");
  assert.equal(a.avatar.canComposeSeated,false,"full model never accepts the classic static body");
  assert.equal(a.models.at(-1).idle,1,"the r21 profile runs its own Idle");
  assert.equal(a.models.at(-1).loops,true,"the real SDK needs its Idle loop enabled explicitly");
  assert.equal(a.models.at(-1).loopFade,false);
  assert.equal(a.shell.dataset.view,"profile");
  assert.equal(a.room.dataset.room,"bedroom");
  assert.equal(await a.avatar.selectModel("classic"),true); await flush();
  assert.equal(a.avatar.usesSeatedBody,true);
  assert.equal(a.room.dataset.seatedReady,"true","the classic body reattaches after returning");

  // A queued return must wait for the obsolete candidate to finish and release.
  const delayed = a.hold("next");
  const obsolete = a.avatar.selectModel("next"); await flush();
  const newest = a.avatar.selectModel("classic"); await flush();
  assert.equal(a.pending,1);
  const loadCount = a.events.filter(event=>event.startsWith("load:")).length;
  await flush();
  assert.equal(a.events.filter(event=>event.startsWith("load:")).length,loadCount);
  delayed.resolve();
  assert.equal(await obsolete,false); assert.equal(await newest,true); await flush();
  assert.equal(a.avatar.state.modelId,"classic");
  const oldCandidate = a.models.filter(model=>model.id==="next").at(-1);
  assert.equal(oldCandidate.destroyed,true);
  assert.equal(oldCandidate.idle,undefined);

  // Failure restores the default, without two models or an endless retry loop.
  a.failNext("next"); assert.equal(await a.avatar.selectModel("next"),false); await flush();
  assert.equal(a.avatar.state.modelId,"classic");
  assert.equal(a.avatar.state.status,"ready");
  assert.equal(a.room.dataset.seatedReady,"true");
  assert(a.avatar.state.message,"a failed request must be visible even after recovery");
  a.failNext("next"); a.failNext("classic");
  const beforeFailure = a.events.length;
  assert.equal(await a.avatar.selectModel("next"),false); await flush();
  assert.equal(a.avatar.state.status,"error");
  assert.equal(a.avatar.ready,false); assert.equal(a.active.size,0);
  assert.equal(a.avatar.usesSeatedBody,false);
  assert.equal(a.events.slice(beforeFailure).filter(event=>event.startsWith("load:")).length,2,
    "one candidate attempt and one default fallback only");
  assert.equal(await a.avatar.selectModel("classic"),true); await flush();
  assert.equal(a.avatar.ready,true);
  assert.equal(a.maximum,1); assert.equal(a.maximumPending,1);

  const nextDefault = await client({defaultId:"next", reactions:true});
  assert.equal(nextDefault.avatar.state.modelId,"next");
  assert.deepEqual(nextDefault.events,["load:next","created:next"],"only the default model is allocated");
  const r21 = nextDefault.models[0];
  const cameraClassic = a.models.at(-1);
  nextDefault.room.dataset.portraitReady = "true";
  for (const room of ["bedroom", "kitchen"]) {
    for (const [view, width, height] of [["home", 413, 735], ["profile", 400, 220], ["home", 845, 223]]) {
      for (const client of [a, nextDefault]) {
        client.room.dataset.room = room;
        client.shell.dataset.view = view;
        client.target.clientWidth = width;
        client.target.clientHeight = height;
        client.avatar.resize();
      }
      const expected = [
        cameraClassic.position.x + (1745 - 1920) * cameraClassic.scale.x,
        cameraClassic.position.y + (871 - 2080) * cameraClassic.scale.y,
        365 * cameraClassic.scale.x,
      ];
      const actual = [
        r21.position.x,
        r21.position.y + (761 - 2500) * r21.scale.y,
        289 * r21.scale.x,
      ];
      actual.forEach((value, i) => assert(Math.abs(value - expected[i]) < .01,
        `${room} ${view} ${width}x${height}: r21 eyes use the classic camera (${i})`));
    }
  }
  const groups = ["Neutral","Playful","Excited","Curious","Tender","Reassuring","Serious"];
  for (const group of groups) {
    nextDefault.avatar.setIntent(group.toLowerCase());
    nextDefault.avatar.setIntent(group.toLowerCase());
  }
  assert.deepEqual(r21.motions.slice(1), groups.flatMap(group =>
    [0,1].map(index => ({group,index,priority:3}))));
  nextDefault.avatar.setIntent("neutral");
  nextDefault.avatar.setSpeaking(false);
  nextDefault.avatar.setIntent("neutral");
  assert.equal(r21.expressions.at(-1),"Blink");
  nextDefault.avatar.setSpeaking(true);
  nextDefault.avatar.setMouth(.53);
  r21.internalModel.emit("afterMotionUpdate");
  r21.internalModel.emit("beforeModelUpdate");
  assert.equal(r21.blinked,true,"r21 blinks during a motion");
  assert.deepEqual(r21.lastParameter,{id:"ParamMouthOpenY",value:.53});
  await flush();
  const beforeBlinkEnds = r21.neutral;
  nextDefault.runTimers(260);
  assert.equal(r21.neutral,beforeBlinkEnds + 1,"a blink releases before the reply ends");
  nextDefault.avatar.setIntent("playful");
  assert.equal(await nextDefault.avatar.selectModel("classic"),true);
  const classic = nextDefault.models.at(-1);
  const neutralOnClassic = classic.neutral;
  nextDefault.runTimers(260);
  nextDefault.runTimers(12000);
  assert.equal(classic.neutral,neutralOnClassic,"old expression callbacks cannot reach the new model");
  nextDefault.applications[0].ticker.callback();
  assert.deepEqual(classic.lastParameter,{id:"ParamMouthOpenY",value:0});
  assert.equal(await nextDefault.avatar.selectModel("next"),true);
  const replacement = nextDefault.models.at(-1);
  replacement.internalModel.emit("beforeModelUpdate");
  assert.deepEqual(replacement.lastParameter,{id:"ParamMouthOpenY",value:0});
  assert.equal(replacement.expressions.length,0,"previous-model expressions are cleared on release");

  const hidden = await client({hidden:true});
  assert.equal(hidden.models.at(-1).autoUpdate,false);
  assert.equal(await hidden.avatar.selectModel("next"),true); await flush();
  assert.equal(hidden.models.at(-1).autoUpdate,false,"replacement remains paused while the page is hidden");
  assert.equal(hidden.applications.at(-1).ticker.running,false);
  hidden.hide(false);
  assert.equal(hidden.models.at(-1).autoUpdate,true);
  assert.equal(hidden.applications.at(-1).ticker.running,true);

  const lateBody = await client({delayBodyImage:true});
  assert.equal(lateBody.avatar.ready,true);
  assert.equal(lateBody.room.dataset.seatedReady,"false");
  assert.equal(await lateBody.avatar.selectModel("next"),true); await flush();
  lateBody.completeBodyImages(); await flush();
  assert.equal(lateBody.avatar.state.modelId,"next");
  assert.equal(lateBody.room.dataset.seatedReady,"false","a late classic image cannot attach to the new full model");
  assert.equal(lateBody.sprites.length,0);

  // A partial compositor failure keeps the DOM seated body and only the live head.
  const domFallback = await client({failCompositionMount:true});
  assert.equal(domFallback.avatar.state.status,"ready");
  assert.equal(domFallback.room.dataset.seatedReady,"true");
  assert.equal(domFallback.room.dataset.seatedCompositor,"false");
  assert(domFallback.body.src,"the DOM body remains available after compositor failure");
  domFallback.applications[0].ticker.callback();
  assert.equal(domFallback.isolationSyncs[0].at(-1),true,
    "each fallback frame keeps the live standing body hidden behind the DOM seated body");
  assert.equal(domFallback.sprites.length,1);
  assert.equal(domFallback.sprites[0].destroyed,true);
  assert.equal(domFallback.sprites[0].texture.destroyed,true,"release the partial body texture");
  assert.equal(domFallback.sprites[0].texture.baseTexture.destroyed,true,"release its underlying resource");
  assert.equal(domFallback.compositionLayers.length,1);
  assert.equal(domFallback.compositionLayers[0].destroyed,true,"release the partial rear layer");
  assert.deepEqual(domFallback.applications[0].stage.children,[domFallback.models[0]],
    "the stage contains no abandoned compositor layer");
  assert.equal(await domFallback.avatar.selectModel("next"),true); await flush();
  assert.equal(domFallback.room.dataset.seatedReady,"false");
  assert.equal(domFallback.body.src,"");
  assert.equal(domFallback.models[0].destroyed,true);
  assert.deepEqual(domFallback.applications[0].stage.children,[domFallback.models.at(-1)]);
  assert.equal(domFallback.maximum,1);

  const early = await client({initialError:true});
  assert.equal(early.avatar.state.status,"error");
  assert.equal(early.events.filter(event=>event.startsWith("load:")).length,1,"no retry loop on initial failure");
  assert.equal(await early.avatar.selectModel("classic"),true); await flush();
  assert.equal(early.avatar.state.status,"ready");

  // A cleanup error must not be bypassed by choosing another option afterward.
  const brokenBody = await client();
  brokenBody.sprites[0].destroy = () => { throw new Error("body texture release failed"); };
  assert.equal(await brokenBody.avatar.selectModel("next"),false);
  assert.equal(brokenBody.avatar.state.status,"error");
  const bodyFailureLoads = brokenBody.events.filter(event=>event.startsWith("load:")).length;
  assert.equal(await brokenBody.avatar.selectModel("classic"),false);
  assert.equal(await brokenBody.avatar.selectModel("next"),false);
  assert.equal(brokenBody.events.filter(event=>event.startsWith("load:")).length,bodyFailureLoads,
    "do not allocate again after a partial composition cleanup");

  const brokenLease = await client();
  brokenLease.models[0].destroy = () => { throw new Error("model release failed"); };
  assert.equal(await brokenLease.avatar.selectModel("next"),false);
  assert.equal(brokenLease.avatar.state.status,"error");
  const leaseFailureLoads = brokenLease.events.filter(event=>event.startsWith("load:")).length;
  assert.equal(await brokenLease.avatar.selectModel("classic"),false);
  assert.equal(brokenLease.events.filter(event=>event.startsWith("load:")).length,leaseFailureLoads,
    "do not allocate a replacement when the previous model may remain in memory");
  console.log("Avatar lifecycle: one model, serialized stale loads, static-body isolation, fallback and visibility PASS");
})().catch(error=>{console.error(error);process.exitCode=1;});
