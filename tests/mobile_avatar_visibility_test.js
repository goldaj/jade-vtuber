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
  const metrics = {start:0,stop:0, idle:0, resize:0, expressions:0, loaded:0, destroyed:0};
  let observed = null;
  const model = {
    autoUpdate:true,
    width:180, height:220,
    scale:{x:1,y:1,set(v){this.x=v;this.y=v;}},
    position:{set(){}}, anchor:{set(){}},
    internalModel:{
      coreModel:{getDrawableRenderOrders(){return [0];}, setParameterValueById(){}},
      motionManager:{expressionManager:{resetExpression(){}}},
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
    setTimeout:()=>1,clearTimeout(){},console,
    CSS:{supports:()=>true},
  };
  vm.runInNewContext(source, context, {filename:"avatar.js"});
  for(let n=0;n<20;n++) await Promise.resolve();
  assert.equal(metrics.loaded,1);
  assert.equal(metrics.idle,1, "no duplicate Idle starts after visibility changes");
  assert.equal(metrics.stop,hiddenAtStart?1:1, "new ticker stopped until model load");
  if(hiddenAtStart) {
    assert.equal(metrics.start,0);
    assert.equal(model.autoUpdate,true, "initial autoUpdate not altered until model ready");
  } else {
    assert.equal(metrics.start,1);
  }
  return {metrics,document,handlers,target,model,window,getObserver:()=>observed};
}

(async()=>{
  const x=await run();
  x.document.hidden=true;
  x.handlers.visibilitychange();
  assert.equal(x.metrics.stop,2);
  assert.equal(x.model.autoUpdate,false);
  x.window.JadeAvatar.setMouth(0.8); // state can change without GPU rendering
  x.document.hidden=false;
  x.handlers.visibilitychange();
  assert.equal(x.metrics.start,2);
  assert.equal(x.model.autoUpdate,true);
  x.getObserver()([{isIntersecting:false}]);
  assert.equal(x.metrics.stop,3);
  x.getObserver()([{isIntersecting:true}]);
  assert.equal(x.metrics.start,3);
  x.target.isConnected=false;
  x.handlers.visibilitychange();
  assert.equal(x.metrics.stop,4);
  x.target.isConnected=true;
  x.handlers.visibilitychange();
  assert.equal(x.metrics.start,4);
  assert.equal(x.metrics.idle,1, "resume must not replay Idle");
  assert.equal(x.metrics.loaded,1, "resume must not reload model");
  assert.equal(x.metrics.destroyed,0);

  const old=await run({intersection:false});
  assert.equal(old.metrics.start,1);
  old.document.hidden=true;
  old.handlers.visibilitychange();
  assert.equal(old.metrics.stop,2);
  const initiallyHidden=await run({hiddenAtStart:true});
  assert.equal(initiallyHidden.metrics.start,0);
  initiallyHidden.document.hidden=false;
  initiallyHidden.handlers.visibilitychange();
  assert.equal(initiallyHidden.metrics.start,1);

  process.stdout.write("VIS-04 mobile Live2D visibility: PASS\n");
})().catch(err=>{console.error(err);process.exitCode=1;});
