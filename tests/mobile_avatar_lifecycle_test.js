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
    defaultId = "classic", reactions = false, random = Math.random} = {}) {
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
  let timerSequence = 0, now = 10;
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
      this.ticker = {running:false, callbacks:[], start(){this.running = true;}, stop(){this.running = false;},
        add(callback){this.callbacks.push(callback);}, remove(){}, callback(){this.callbacks.forEach(run => run());}};
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
      coreModel:{
        getDrawableRenderOrders(){return [0];},
        getParameterValueById(id){return model.parameters.get(id)?.value ?? (id === "ParamBreath" ? .43 : 0);},
        setParameterValueById(id,value,weight = 1){
          model.lastParameter={id,value};
          model.parameters.set(id, {value,weight});
        },
        addParameterValueById(id,value,weight = 1){
          model.shakeParameters.set(id, value);
          model.addedParameters.set(id, {value,weight});
        },
        multiplyParameterValueById(id,factor,weight = 1){
          const original = model.parameters.get(id).value;
          model.parameters.set(id, {value:original * (1 + (factor - 1) * weight),weight});
        },
      },
      draw(){},eyeBlink:{updateParameters(core){
        model.blinked = true;
        core.setParameterValueById("ParamEyeLOpen", model.blinkOpening ?? 1);
        core.setParameterValueById("ParamEyeROpen", model.blinkOpening ?? 1);
      }},
      motionManager:Object.assign(new EventEmitter(), {
        expressionManager:{defaultExpression:{}, resetExpression(){model.neutral = (model.neutral || 0) + 1;}},
      }),
    });
    model.shakeParameters = new Map();
    model.parameters = new Map();
    model.addedParameters = new Map();
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
    performance:{now(){return now;}},
    Math:Object.assign(Object.create(Math), {random}),
    setTimeout(callback, delay){const id = ++timerSequence; timers.set(id, {callback,delay}); return id;},
    clearTimeout(id){timers.delete(id);}};
  vm.createContext(context);
  vm.runInContext(seatedSource,context,{filename:"seated-scene.js"});
  vm.runInContext(source,context,{filename:"avatar.js"});
  await flush();
  return {avatar:window.JadeAvatar,window,room,shell,document,target,fallback,body,models,active,events,states,applications,sprites,compositionLayers,isolationSyncs,
    advanceTime(ms){now += ms;},
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

  const draws = [.12, .2, .84];
  for (let i = 0; i < 6; i++) draws.push(.15, .85);
  let drawCount = 0;
  const nextDefault = await client({defaultId:"next", reactions:true, random:() => {
    drawCount++;
    return draws.shift() ?? .3;
  }});
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
      if (room === "bedroom" && view === "home" && width < height) {
        // The canvas extends below the lifted portrait frame, while the camera still uses the frame.
        nextDefault.target.parentElement = {clientHeight:height};
        nextDefault.target.clientHeight = height + 88;
        nextDefault.avatar.resize();
        nextDefault.target.parentElement = null;
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
  const mouthForms = {
    Neutral:[.06,0], Playful:[.40,.26], Excited:[.56,.29], Curious:[-.28,0],
    Tender:[.23,.06], Reassuring:[.34,.16], Serious:[-.74,-.74],
  };
  const actingSamples = {Playful:[],Serious:[]};
  for (const group of groups) {
    for (let variant = 0; variant < 2; variant++) {
      nextDefault.avatar.setIntent(group.toLowerCase());
      nextDefault.advanceTime(150);
      r21.addedParameters.clear();
      r21.internalModel.emit("afterMotionUpdate");
      r21.internalModel.emit("beforeModelUpdate");
      const [closed, open] = mouthForms[group];
      assert.deepEqual(r21.parameters.get("ParamMouthForm"),{value:closed,weight:1});
      if (Object.hasOwn(actingSamples, group)) {
        actingSamples[group].push({
          brow:r21.addedParameters.get("ParamBrowLAngle").value,
          posture:r21.addedParameters.get(group === "Playful" ? "ParamBodyAngleZ" : "ParamBodyAngleX").value,
          gaze:r21.addedParameters.get("ParamEyeBallX")?.value ?? 0,
          lids:["ParamEyeLOpen","ParamEyeROpen"].map(id => r21.parameters.get(id).value),
        });
      }
      assert.equal(r21.addedParameters.has("ParamEyeLOpen"),false,"the expression leaves blinking independent");
      nextDefault.avatar.setMouth(1);
      r21.internalModel.emit("beforeModelUpdate");
      assert(Math.abs(r21.parameters.get("ParamMouthForm").value - open) < 1e-8,
        group + " retains its intended shape during open vowels");
      nextDefault.avatar.setMouth(0);
    }
    if (group === "Neutral") nextDefault.avatar.setIntent("neutral");
  }
  assert.deepEqual(r21.motions.slice(1), groups.flatMap(group =>
    (group === "Neutral" ? [0,0,1] : [0,1]).map(index => ({group,index,priority:3}))));
  assert.deepEqual(actingSamples, {
    Playful:[{brow:-.23,posture:-2.4,gaze:-.10,lids:[.91,.97]},{brow:-.23,posture:2.4,gaze:.10,lids:[.97,.91]}],
    Serious:[{brow:.16,posture:.7,gaze:0,lids:[.98,.98]},{brow:.16,posture:-.7,gaze:0,lids:[.98,.98]}],
  });

  let earVariant = .24;
  const earClient = await client({defaultId:"next",reactions:true,random:() => earVariant});
  const ears = earClient.models[0];
  const earIds = ["ParamJadeEarFollowL","ParamJadeEarFollowR"];
  function renderEars(ms) {
    earClient.advanceTime(ms);
    ears.internalModel.emit("afterMotionUpdate");
    ears.internalModel.emit("beforeModelUpdate");
    return earIds.map(id => ears.addedParameters.get(id).value);
  }
  assert.deepEqual(renderEars(0), [0,0]);
  ears.internalModel.coreModel.setParameterValueById("ParamBreath", .83);
  const inhaling = renderEars(25);
  assert(inhaling[0] > inhaling[1] && inhaling[1] > 0 && inhaling[0] < .04,
    "a real breath lifts both ears with distinct, gradual delays");
  for (let i = 0; i < 8; i++) renderEars(100);
  assert(renderEars(25).every(lift => lift > .11), "a sustained inhalation reaches the tips");
  ears.internalModel.coreModel.setParameterValueById("ParamBreath", .43);
  for (let i = 0; i < 16; i++) renderEars(100);
  function earBeat(intent, age) {
    earClient.avatar.setIntent(intent,{deferMotion:true});
    return renderEars(age);
  }
  const neutralEars = earBeat("neutral",360);
  const playfulA = earBeat("playful",240);
  earVariant = .76;
  const playfulB = earBeat("playful",240);
  const excitedEars = earBeat("excited",310);
  const curiousEars = earBeat("curious",610);
  const tenderEars = earBeat("tender",1200);
  const reassuringEars = earBeat("reassuring",950);
  const seriousEars = earBeat("serious",630);
  assert(neutralEars.every(lift => lift > .08 && lift < .15));
  assert(playfulA[0] > .38 && playfulA[1] < -.08 && playfulB[0] < -.08 && playfulB[1] > .38);
  assert(excitedEars.every(lift => lift > .46));
  assert(curiousEars[0] < -.20 && curiousEars[1] > .46);
  assert(tenderEars.every(lift => lift < -.20));
  assert(reassuringEars.every(lift => lift > .20 && lift < .26));
  assert(seriousEars.every(lift => lift < -.32));
  earClient.avatar.resetIntent();
  assert(renderEars(200).every(lift => Math.abs(lift) < .001), "interruption releases both ears to breathing");

  const beforeSpeech = r21.motions.length;
  assert.equal(nextDefault.avatar.setIntent("serious",{deferMotion:true}),true);
  nextDefault.avatar.startReplyMotion(200);
  nextDefault.advanceTime(150);
  r21.internalModel.emit("beforeModelUpdate");
  assert.deepEqual(r21.parameters.get("ParamMouthForm"),{value:-.74,weight:1});
  assert.equal(r21.motions.length,beforeSpeech,"the face precedes the motion and voice");
  nextDefault.advanceTime(50);
  nextDefault.runTimers(200);
  assert.deepEqual(r21.motions.at(-1),{group:"Serious",index:0,priority:3});
  nextDefault.avatar.startReplyMotion(200);
  nextDefault.runTimers(200);
  assert.equal(r21.motions.length,beforeSpeech + 1,"one gesture per reply");
  assert.equal(drawCount,16,"one random draw per reply");
  nextDefault.avatar.setSpeaking(true);
  nextDefault.avatar.setMouth(.53);
  r21.internalModel.coreModel.setParameterValueById("ParamAngleX", 25);
  r21.blinkOpening = 0;
  r21.internalModel.emit("afterMotionUpdate");
  r21.internalModel.emit("beforeModelUpdate");
  assert.equal(r21.blinked,true,"r21 blinks during a motion");
  assert.equal(r21.parameters.get("ParamEyeLOpen").value,0,"the held pose preserves a fully closed blink");
  assert.equal(r21.parameters.get("ParamEyeROpen").value,0);
  delete r21.blinkOpening;
  assert.deepEqual(r21.lastParameter,{id:"ParamMouthOpenY",value:.53});
  r21.internalModel.coreModel.setParameterValueById("ParamAngleX", 0);
  nextDefault.avatar.setSpeaking(false);
  nextDefault.avatar.setMouth(0);
  nextDefault.avatar.finishReply(true);
  nextDefault.advanceTime(350);
  nextDefault.avatar.setSpeaking(true);
  nextDefault.runTimers(600);
  r21.internalModel.emit("beforeModelUpdate");
  assert.deepEqual(r21.parameters.get("ParamMouthForm"),{value:-.74,weight:1},"resuming after a pause keeps the face");
  assert.equal(r21.motions.length,beforeSpeech + 1,"resuming the same reply does not replay its motion");
  nextDefault.avatar.setSpeaking(false);
  nextDefault.avatar.finishReply(true);
  nextDefault.advanceTime(600);
  r21.internalModel.emit("beforeModelUpdate");
  assert.deepEqual(r21.lastParameter,{id:"ParamMouthOpenY",value:0});
  assert.deepEqual(r21.parameters.get("ParamMouthForm"),{value:-.74,weight:1},"the closed mouth stays serious");
  nextDefault.runTimers(600);
  nextDefault.advanceTime(110);
  r21.internalModel.emit("beforeModelUpdate");
  assert.deepEqual(r21.parameters.get("ParamMouthForm"),{value:-.74,weight:.5});
  assert.deepEqual(r21.addedParameters.get("ParamBrowLAngle"),{value:.16,weight:.5});
  nextDefault.avatar.setIntent("playful",{deferMotion:true});
  nextDefault.avatar.startReplyMotion(200);
  nextDefault.runTimers(220);
  nextDefault.advanceTime(200);
  r21.internalModel.emit("beforeModelUpdate");
  assert.deepEqual(r21.parameters.get("ParamMouthForm"),{value:.40,weight:1},"an old fade cannot clear a new reply");
  nextDefault.avatar.setMouth(1);
  r21.internalModel.emit("beforeModelUpdate");
  assert.deepEqual(r21.parameters.get("ParamMouthForm"),{value:.26,weight:1},"open vowels soften the playful mouth");
  function smileOpening(yaw, envelope) {
    r21.internalModel.coreModel.setParameterValueById("ParamAngleX", yaw);
    nextDefault.avatar.setMouth(envelope);
    r21.internalModel.emit("beforeModelUpdate");
    return r21.lastParameter.value;
  }
  assert.equal(smileOpening(0,1),1);
  const leftProfile = smileOpening(-23,1);
  assert(leftProfile > .85 && leftProfile < .90, "the strongest vowel is softened in three-quarter view");
  assert.equal(smileOpening(23,1),leftProfile);
  assert(smileOpening(23,.3) > .29, "small syllables remain visible");
  const profileOpenings = [0,.25,.5,.75,1].map(envelope => smileOpening(30,envelope));
  assert.equal(profileOpenings[0],0);
  assert(profileOpenings.slice(1).every((opening,index) => opening > profileOpenings[index]),
    "the profile adjustment preserves the volume dynamics");
  smileOpening(0,0);
  assert.equal(await nextDefault.avatar.selectModel("classic"),true);
  const classic = nextDefault.models.at(-1);
  const neutralOnClassic = classic.neutral;
  nextDefault.runTimers(200);
  nextDefault.runTimers(600);
  nextDefault.runTimers(220);
  nextDefault.runTimers(12000);
  assert.equal(classic.neutral,neutralOnClassic,"old expression callbacks cannot reach the new model");
  nextDefault.applications[0].ticker.callback();
  assert.deepEqual(classic.lastParameter,{id:"ParamMouthOpenY",value:0});
  assert.equal(await nextDefault.avatar.selectModel("next"),true);
  const replacement = nextDefault.models.at(-1);
  replacement.internalModel.emit("beforeModelUpdate");
  const firstMotion = deferred(), nextMotion = deferred();
  replacement.internalModel.motionManager.loadMotion = group =>
    group === "Serious" ? firstMotion.promise : nextMotion.promise;
  nextDefault.avatar.setIntent("serious",{deferMotion:true});
  nextDefault.avatar.startReplyMotion();
  nextDefault.avatar.resetIntent();
  nextDefault.avatar.setIntent("playful",{deferMotion:true});
  nextDefault.avatar.startReplyMotion();
  firstMotion.resolve({});
  await flush();
  assert.deepEqual(replacement.motions.map(({group}) => group),["Idle"],
    "a late clip is never reserved after its reply has been cancelled");
  nextMotion.resolve({});
  await flush();
  assert.deepEqual(replacement.motions.map(({group}) => group),["Idle","Playful"]);
  nextDefault.avatar.resetIntent();
  assert.deepEqual(replacement.lastParameter,{id:"ParamMouthOpenY",value:0});
  assert.equal(replacement.expressions.length,0,"previous-model expressions are cleared on release");

  const touch = await client({defaultId:"next"});
  const standing = touch.models[0];
  touch.shell.dataset.view = "home";
  touch.room.dataset.room = "kitchen";
  touch.target.getBoundingClientRect = () => ({left:12, top:42, right:402, bottom:732, width:390, height:690});
  touch.room.getBoundingClientRect = touch.target.getBoundingClientRect;
  const pose = () => [standing.position.x, standing.position.y, standing.scale.x];
  touch.avatar.resize();
  const initial = pose();
  const eye = () => [12 + standing.position.x, 42 + standing.position.y - .35 * 5000 * standing.scale.y];
  assert(touch.avatar.isModelAt(...eye()),"a contact on Jade's head can start a gesture");
  const frame = touch.avatar.getTouchFrame();
  assert(!touch.avatar.isModelAt(frame.left + 1, frame.top + 1),"blank corners cannot start a grab");
  const visibleFaceMesh = {
    ids:["JAD_R21_RESTORED_FACE"], opacities:[1], indices:[[0,1,2]],
    vertexPositions:[[-.1,.4,.1,.4,0,.55]],
  };
  standing.internalModel.coreModel.getModel = () => ({canvasinfo:{CanvasWidth:3840,CanvasHeight:5000,PixelsPerUnit:3840},
    drawables:visibleFaceMesh});
  assert(touch.avatar.isModelAt(...eye()),"the hit test uses the visible Cubism triangle");
  visibleFaceMesh.opacities[0] = 0;
  assert(!touch.avatar.isModelAt(...eye()),"an invisible model mesh cannot start a grab");
  delete standing.internalModel.coreModel.getModel;
  const startPinch = eye();
  assert(touch.avatar.zoomView(1.5, ...startPinch));
  assert(Math.abs(standing.scale.x - initial[2] * 1.5) < 1e-9);
  eye().forEach((coordinate, i) => assert(Math.abs(coordinate - startPinch[i]) < 1e-9,
    "zoom keeps the character point under the centre of the fingers"));
  assert(touch.avatar.moveView(11, 7));
  eye().forEach((coordinate, i) => assert(Math.abs(coordinate - startPinch[i] - [11, 7][i]) < 1e-9,
    "translation follows the finger"));
  assert(touch.avatar.moveView(-1e4, -1e4));
  const clipped = touch.avatar.getTouchFrame();
  assert(clipped && clipped.left >= 12 && clipped.right <= 402 && clipped.top >= 42 && clipped.bottom <= 732,
    "offscreen drag leaves a usable clipped frame");
  assert([ [.50,.15], [.50,.30], [.50,.48], [.447,.73], [.543,.73] ].some(([x,y]) =>
    touch.avatar.isModelAt(12 + standing.position.x + (x - .5) * 3840 * standing.scale.x,
      42 + standing.position.y + (y - .5) * 5000 * standing.scale.y)),
    "a solid part remains reachable when panning diagonally past the edges");
  const adjusted = pose();
  touch.shell.dataset.view = "chat";
  touch.avatar.resize();
  assert.equal(touch.avatar.getTouchFrame(), null, "mini-scenes do not expose touch framing");
  assert.equal(touch.avatar.moveView(10, 10), false);
  assert.notDeepEqual(pose(), adjusted);
  touch.shell.classList.add("is-room-only");
  touch.avatar.resize();
  assert(touch.avatar.getTouchFrame(), "immersive framing works even from another tab");
  touch.shell.classList.remove("is-room-only");
  touch.shell.dataset.view = "home";
  touch.avatar.resize();
  pose().forEach((value, i) => assert(Math.abs(value - adjusted[i]) < 1e-9,
    "the custom framing comes back on Accueil"));
  assert(touch.avatar.resetView());
  assert.deepEqual(pose(), initial, "Recentrer restores the exact original transform");
  assert(touch.avatar.zoomView(1.2, ...eye()));
  assert(touch.avatar.moveView(13, 9));
  const shakePose = pose();
  const shakeLayer = standing.parent;
  const shakeMotionCount = standing.motions.length;
  touch.avatar.setMouth(.35);
  assert(touch.avatar.nudgeFromShake(1, .5));
  touch.advanceTime(70);
  touch.applications[0].ticker.callback();
  standing.internalModel.emit("afterMotionUpdate");
  standing.internalModel.emit("beforeModelUpdate");
  assert(shakeLayer.position.x > 55, "a strong shake displaces the whole avatar visibly");
  assert(shakeLayer.position.y > 20, "the motion follows the direction of the shake");
  assert(standing.shakeParameters.get("ParamAngleX") > 20, "shake noticeably drives the rig's physics inputs");
  assert(touch.avatar.isModelAt(eye()[0] + shakeLayer.position.x, eye()[1] + shakeLayer.position.y),
    "the shifted character is still hittable");
  assert.equal(standing.motions.length, shakeMotionCount, "shake leaves the active motion playing");
  assert.deepEqual(standing.lastParameter, {id:"ParamMouthOpenY", value:.35}, "shake leaves lip sync active");
  assert.deepEqual(pose(), shakePose, "shake keeps the custom placement and zoom");
  touch.advanceTime(100);
  touch.applications[0].ticker.callback();
  assert(shakeLayer.position.x < -40, "the avatar visibly swings back before settling");
  standing.shakeParameters.clear();
  touch.advanceTime(1000);
  touch.applications[0].ticker.callback();
  standing.internalModel.emit("afterMotionUpdate");
  assert.equal(standing.shakeParameters.size, 0, "the impulse expires");
  assert.equal(shakeLayer.position.x, 0, "the avatar returns to exactly the chosen framing");
  assert.equal(shakeLayer.position.y, 0);
  assert(touch.avatar.nudgeFromShake(1, .5));
  touch.advanceTime(70);
  touch.applications[0].ticker.callback();
  const shown = [standing.position.x + shakeLayer.position.x, standing.position.y + shakeLayer.position.y];
  assert(touch.avatar.moveView(5, -7));
  assert.deepEqual(pose(), [shown[0] + 5, shown[1] - 7, shakePose[2]],
    "a manual drag takes over the shown pose without snapping back");
  assert.equal(shakeLayer.position.x, 0);
  assert(touch.avatar.moveView(-1e4, -1e4));
  const edgePose = pose();
  assert(touch.avatar.nudgeFromShake(-1, -1));
  touch.advanceTime(70);
  touch.applications[0].ticker.callback();
  assert([ [.50,.15], [.50,.30], [.50,.48], [.447,.73], [.543,.73] ].some(([x,y]) =>
    touch.avatar.isModelAt(12 + standing.position.x + shakeLayer.position.x + (x - .5) * 3840 * standing.scale.x,
      42 + standing.position.y + shakeLayer.position.y + (y - .5) * 5000 * standing.scale.y)),
    "an outward shake still leaves a solid part reachable at the edge");
  touch.avatar.stopShake();
  assert.deepEqual(pose(), edgePose, "even a clamped shake returns exactly to the chosen edge placement");
  touch.avatar.resetView();
  touch.shell.dataset.view = "profile";
  assert(!touch.avatar.nudgeFromShake(1, 1), "a mini-scene cannot receive a shake");
  touch.shell.classList.add("is-room-only");
  assert(touch.avatar.nudgeFromShake(1, 1), "the fullscreen scene can receive a shake");
  touch.advanceTime(70);
  touch.applications[0].ticker.callback();
  assert(shakeLayer.position.x > 55);
  touch.hide(true);
  assert.equal(shakeLayer.position.x, 0, "backgrounding immediately clears the transient displacement");
  assert(!touch.avatar.nudgeFromShake(1, 1), "the backgrounded page cannot receive a shake");
  touch.hide(false);
  standing.internalModel.emit("afterMotionUpdate");
  assert.equal(standing.shakeParameters.size, 0, "an old impulse cannot resume from the background");
  assert.equal(await touch.avatar.selectModel("classic"), true);
  assert(shakeLayer.destroyed, "switching models releases the parent's transient transform");
  assert.equal(touch.avatar.getTouchFrame(), null, "classic is outside the touch feature");
  assert(!touch.avatar.nudgeFromShake(1, 1), "classic cannot receive a shake");

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
  assert.deepEqual(domFallback.applications[0].stage.children,[domFallback.models.at(-1).parent]);
  assert.deepEqual(domFallback.models.at(-1).parent.children,[domFallback.models.at(-1)]);
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
