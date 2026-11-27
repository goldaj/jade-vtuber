/* r21 VIS-04/VIS-07 lifecycle with inert browser/SDK adapters; no legacy model. */
"use strict";
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const source = fs.readFileSync(path.join(__dirname, "../src/jade_runtime/mobile_web/avatar.js"), "utf8");
const palette = JSON.parse(fs.readFileSync(path.join(__dirname, "../src/jade_runtime/mobile_web/intent-visuals.json"), "utf8"));
const {EventEmitter} = require("node:events");
const point = () => ({x:0,y:0,set(x,y=x){this.x=x;this.y=y;}});

async function run({intersection = true, hiddenAtStart = false} = {}) {
  const handlers = {};
  const target = {
    clientWidth: 480, clientHeight: 800, isConnected: true,
    getClientRects() { return [{}]; },
    appendChild() {},
  };
  const fallback = {classList:{add(){},remove(){}}};
  const status = {textContent:""};
  const mood = {textContent:""};
  const room = {dataset:{room:"bedroom"},addEventListener(){}};
  const shell = {dataset:{view:"home"},classList:{contains(){return false;}}};
  const document = {
    hidden:hiddenAtStart,
    querySelector(selector){return {".room":room,".shell":shell}[selector] || null;},
    getElementById(id) {
      return {"avatar-container":target,"avatar-fallback":fallback,
              "avatar-state":status,"mood-line":mood}[id];
    },
    addEventListener(name, handler) { handlers[name] = handler; },
  };
  const metrics = {start:0,stop:0,idle:0,resize:0,loaded:0,destroyed:0};
  let now = 0;
  let nextTimer = 0;
  const timers = new Map();
  const clock = {
    get pending() { return timers.size; },
    advance(ms) {
      const until = now + ms;
      while (true) {
        const due = [...timers].filter(([, task]) => task.at <= until)
          .sort((a, b) => a[1].at - b[1].at)[0];
        if (!due) break;
        now = due[1].at;
        timers.delete(due[0]);
        due[1].fn();
      }
      now = until;
    },
  };
  let observed = null;
  const parameters = new Map();
  const model = {
    autoUpdate:true,
    get width(){return 3840 * this.scale.x;},
    get height(){return 5000 * this.scale.y;},
    scale:{x:1,y:1,set(v){this.x=v;this.y=v;}},
    position:point(),anchor:point(),
    internalModel:Object.assign(new EventEmitter(),{
      coreModel:{
        getDrawableRenderOrders(){return [0];},
        getParameterValueById(id){return parameters.get(id) ?? (id === "ParamBreath" ? .43 : 0);},
        setParameterValueById(id,value){parameters.set(id,value);},
        addParameterValueById(id,value,weight=1){parameters.set(id,(parameters.get(id) ?? 0) + value * weight);},
        multiplyParameterValueById(id,value,weight=1){parameters.set(id,(parameters.get(id) ?? 0) * (1 + (value-1) * weight));},
      },
      eyeBlink:{updateParameters(core){core.setParameterValueById("ParamEyeLOpen",1);core.setParameterValueById("ParamEyeROpen",1);}},
      motionManager:new EventEmitter(),
    }),
    motion(group,index){assert.equal(group,"Idle");assert.equal(index,0);metrics.idle++;return Promise.resolve();},
    frame(){
      parameters.clear();parameters.set("ParamMouthForm",0);
      this.internalModel.emit("afterMotionUpdate");
      this.internalModel.emit("beforeModelUpdate");
      return Object.fromEntries(parameters);
    },
  };
  class Container {
    constructor(){this.position=point();this.children=[];}
    addChild(child){this.children.push(child);child.parent=this;}
  }
  class Application {
    constructor() {
      this.view = {};
      this.stage = new Container();
      this.renderer = {resize(){metrics.resize++;}};
      this.ticker = {
        start(){metrics.start++;},
        stop(){metrics.stop++;},
        add(fn){this.onTick=fn;},
      };
    }
    destroy(){metrics.destroyed++;}
  }
  const PIXI = {
    Application,Container,
    UPDATE_PRIORITY:{LOW:-50},
    live2d:{Live2DModel:{async from(){metrics.loaded++; return model;}}},
  };
  class ResizeObserver {observe(){} disconnect(){}}
  const profile = {id:"next", available:true, manifestUrl:"/models/next/Jade.model3.json",
    presentation:"full", classicIntents:false, idleMotion:"Idle"};
  const window = {PIXI,Live2DCubismCore:{},devicePixelRatio:1,
    JadeModelCatalog:{defaultId:"next", ready:Promise.resolve([profile]),
      get(id){return id === profile.id ? profile : null;}, list(){return [profile];}},
    JadeAvatarModelLoader:{async load(selected){
      assert.equal(selected.id, "next", "the visibility suite only loads r21"); metrics.loaded++;
      return {model, dispose(){model.autoUpdate = false;}};
    }}};
  const context = {
    document,window,ResizeObserver,
    IntersectionObserver:intersection?class {
      constructor(fn){observed=fn;}
      observe(){} disconnect(){}
    }:undefined,
    fetch:async()=>({ok:true, json:async()=>({...palette,enabled:true})}),
    performance:{now:()=>now},
    setTimeout(fn, delay) {
      const id = ++nextTimer;
      timers.set(id, {at:now + delay, fn});
      return id;
    },
    clearTimeout(id) { timers.delete(id); },console,
    CSS:{supports:()=>true},
  };
  vm.runInNewContext(source, context, {filename:"avatar.js"});
  for(let n=0;n<20;n++) await Promise.resolve();
  assert.equal(metrics.loaded,1);
  assert.equal(metrics.idle,1, "no duplicate Idle starts after visibility changes");
  assert.equal(metrics.stop,1, "new ticker stopped until model load");
  assert.equal(window.JadeAvatar.state.modelId,"next");
  if(hiddenAtStart) {
    assert.equal(metrics.start,0);
    assert.equal(model.autoUpdate,false, "shared model updater stopped while initially hidden");
  } else {
    assert.equal(metrics.start,1);
  }
  return {metrics,document,handlers,target,model,window,clock,mood,getObserver:()=>observed};
}

(async()=>{
  const x=await run();
  assert.equal(x.metrics.start,1);
  assert.equal(x.metrics.stop,1);
  assert.equal(x.clock.pending,0);
  assert.equal(x.window.JadeAvatar.setIntent("sad",{deferMotion:true}),true);
  x.clock.advance(150);
  assert.equal(x.model.frame().ParamMouthForm,-1);

  // A hidden app is a hard pause, never six seconds of invisible GPU work.
  x.document.hidden=true;
  x.handlers.visibilitychange();
  assert.equal(x.metrics.stop,2);
  assert.equal(x.model.autoUpdate,false);
  x.window.JadeAvatar.setMouth(0.8); // voice state can still update
  x.document.hidden=false;
  x.handlers.visibilitychange();
  assert.equal(x.metrics.start,2);
  assert.equal(x.model.autoUpdate,true);
  assert.equal(x.model.frame().ParamMouthOpenY,.8,"voice state reaches r21 after resuming");
  assert(Math.abs(x.model.frame().ParamMouthForm + .856) < 1e-9,"the held r21 face remains coupled to the current reply");
  x.window.JadeAvatar.setMouth(0);

  // A brief viewport departure should NOT stop or restart Pixi.
  x.getObserver()([{isIntersecting:false}]);
  assert.equal(x.clock.pending,1,"only one delayed-off timer");
  assert.equal(x.metrics.stop,2);
  x.clock.advance(3500);
  x.getObserver()([{isIntersecting:false}]);
  assert.equal(x.clock.pending,1,"repeat events cannot create a timer storm");
  x.getObserver()([{isIntersecting:true}]);
  assert.equal(x.clock.pending,0,"return cancels the pending pause");
  x.clock.advance(8000);
  assert.equal(x.metrics.stop,2);
  assert.equal(x.metrics.start,2);
  assert.equal(x.model.frame().ParamMouthForm,-1,"brief occlusion preserves the r21 reply pose");

  // A sustained viewport absence is paused after 6.5 seconds.
  x.getObserver()([{isIntersecting:false}]);
  x.clock.advance(6499);
  assert.equal(x.metrics.stop,2);
  x.clock.advance(1);
  assert.equal(x.metrics.stop,3);
  assert.equal(x.model.autoUpdate,false);
  assert.equal(x.clock.pending,0);
  x.getObserver()([{isIntersecting:false}]);
  assert.equal(x.clock.pending,0,"offscreen and stopped remains stopped");
  x.getObserver()([{isIntersecting:true}]);
  assert.equal(x.metrics.start,3);
  assert.equal(x.model.frame().ParamMouthForm,-1,"a paused active reply retains its r21 pose on return");
  assert.equal(x.model.autoUpdate,true);

  // Hard stop while soft timer is pending cancels it synchronously.
  x.getObserver()([{isIntersecting:false}]);
  assert.equal(x.clock.pending,1);
  x.target.isConnected=false;
  x.handlers.visibilitychange();
  assert.equal(x.clock.pending,0);
  assert.equal(x.metrics.stop,4);
  x.clock.advance(9000);
  assert.equal(x.metrics.stop,4);
  x.target.isConnected=true;
  x.getObserver()([{isIntersecting:true}]);
  x.handlers.visibilitychange();
  assert.equal(x.metrics.start,4);
  assert.equal(x.model.frame().ParamMouthForm,-1);
  assert.equal(x.metrics.idle,1,"resume must not replay Idle motion");
  assert.equal(x.metrics.loaded,1,"resume must not reload the model");
  assert.equal(x.metrics.destroyed,0);

  // A second rapid hide/unhide should stop once and resume once.
  x.document.hidden=true;
  x.handlers.visibilitychange();
  x.handlers.visibilitychange();
  assert.equal(x.metrics.stop,5);
  x.document.hidden=false;
  x.handlers.visibilitychange();
  x.handlers.visibilitychange();
  assert.equal(x.metrics.start,5);
  assert.equal(x.model.frame().ParamMouthForm,-1);
  x.window.JadeAvatar.resetIntent();
  assert.equal(x.model.frame().ParamMouthForm,0,"explicit interruption releases the held r21 face");

  const withoutObserver=await run({intersection:false});
  assert.equal(withoutObserver.metrics.start,1);
  withoutObserver.document.hidden=true;
  withoutObserver.handlers.visibilitychange();
  assert.equal(withoutObserver.metrics.stop,2);
  withoutObserver.document.hidden=false;
  withoutObserver.handlers.visibilitychange();
  assert.equal(withoutObserver.metrics.start,2);

  const initiallyHidden=await run({hiddenAtStart:true});
  assert.equal(initiallyHidden.metrics.start,0);
  assert.equal(initiallyHidden.model.autoUpdate,false);
  initiallyHidden.document.hidden=false;
  initiallyHidden.handlers.visibilitychange();
  assert.equal(initiallyHidden.metrics.start,1);
  assert.equal(initiallyHidden.model.frame().ParamMouthForm,0,"initial r21 load has no stale reply pose");
  assert.equal(initiallyHidden.metrics.idle,1);

  console.log("r21 VIS-04+VIS-07: immediate background pause, viewport hysteresis, active reply and single model PASS");
})().catch(err=>{console.error(err);process.exitCode=1;});
