/* VIS-04: simulated browser lifecycle, no GPU, network or AI costs. */
"use strict";
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const source = fs.readFileSync(path.join(__dirname, "../src/jade_runtime/mobile_web/avatar.js"), "utf8");

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
  const document = {
    hidden:hiddenAtStart,
    getElementById(id) {
      return {"avatar-container":target,"avatar-fallback":fallback,
              "avatar-state":status,"mood-line":mood}[id];
    },
    addEventListener(name, handler) { handlers[name] = handler; },
  };
  const metrics = {start:0,stop:0, idle:0, neutral:0, resize:0, expressions:0, loaded:0, destroyed:0};
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
  const model = {
    autoUpdate:true,
    width:180, height:220,
    scale:{x:1,y:1,set(v){this.x=v;this.y=v;}},
    position:{set(){}}, anchor:{set(){}},
    internalModel:{
      coreModel:{getDrawableRenderOrders(){return [0];}, setParameterValueById(){}},
      motionManager:{expressionManager:{resetExpression(){metrics.neutral++;}}},
    },
    motion(group,index){assert.equal(group,"Idle");assert.equal(index,0);metrics.idle++;return Promise.resolve();},
    expression(){metrics.expressions++;return Promise.resolve();},
  };
  class Application {
    constructor() {
      this.view = {};
      this.stage = {addChild(){}};
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
    Application,
    UPDATE_PRIORITY:{LOW:-50},
    live2d:{Live2DModel:{async from(){metrics.loaded++; return model;}}},
  };
  class ResizeObserver {observe(){} disconnect(){}}
  const window = {PIXI,Live2DCubismCore:{},devicePixelRatio:1};
  const context = {
    document,window,ResizeObserver,
    IntersectionObserver:intersection?class {
      constructor(fn){observed=fn;}
      observe(){} disconnect(){}
    }:undefined,
    fetch:async()=>({ok:true, json:async()=>({version:1,enabled:false,intents:{}})}),
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
  assert.equal(metrics.stop,hiddenAtStart?1:1, "new ticker stopped until model load");
  if(hiddenAtStart) {
    assert.equal(metrics.start,0);
    assert.equal(model.autoUpdate,false, "shared model updater stopped while initially hidden");
  } else {
    assert.equal(metrics.start,1);
  }
  return {metrics,document,handlers,target,model,window,clock,getObserver:()=>observed};
}

(async()=>{
  const x=await run();
  assert.equal(x.metrics.start,1);
  assert.equal(x.metrics.stop,1);
  assert.equal(x.clock.pending,0);

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
  assert.equal(x.metrics.neutral,1,"genuine resumption clears obsolete expression");

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
  assert.equal(x.metrics.neutral,1,"brief occlusion must not reset emotion");

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
  assert.equal(x.metrics.neutral,2);
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
  assert.equal(x.metrics.neutral,3);
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
  assert.equal(x.metrics.neutral,4);

  const old=await run({intersection:false});
  assert.equal(old.metrics.start,1);
  old.document.hidden=true;
  old.handlers.visibilitychange();
  assert.equal(old.metrics.stop,2);
  old.document.hidden=false;
  old.handlers.visibilitychange();
  assert.equal(old.metrics.start,2);

  const initiallyHidden=await run({hiddenAtStart:true});
  assert.equal(initiallyHidden.metrics.start,0);
  assert.equal(initiallyHidden.model.autoUpdate,false);
  initiallyHidden.document.hidden=false;
  initiallyHidden.handlers.visibilitychange();
  assert.equal(initiallyHidden.metrics.start,1);
  assert.equal(initiallyHidden.metrics.neutral,0,"initial load is not a resume");
  assert.equal(initiallyHidden.metrics.idle,1);

  process.stdout.write("VIS-04+VIS-07 Live2D visibility hysteresis: PASS\\n");
})().catch(err=>{console.error(err);process.exitCode=1;});
