/* r21-only intention contract and scheduling, with an inert Cubism adapter.
 * This exercises avatar.js; it is not a visual acceptance of the native rig.
 * Run from the full checkout: the private publication preview deliberately
 * excludes this script and jade-modeling, and does not invoke it in its suite.
 */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const {EventEmitter} = require("node:events");
const root = path.join(__dirname, "..");
const web = path.join(root, "src/jade_runtime/mobile_web");
const source = fs.readFileSync(path.join(web, "avatar.js"), "utf8");
const palette = JSON.parse(fs.readFileSync(path.join(web, "intent-visuals.json"), "utf8"));
const bundle = path.join(root, "jade-modeling/assets/live2d/r21_professional_art/livraison/Jade_r21_v45_1/Jade_r21_v45");
const manifest = JSON.parse(fs.readFileSync(path.join(bundle, "Jade_r21_mobile.model3.json"), "utf8"));
const groups = ["Neutral", "Playful", "Excited", "Curious", "Tender", "Reassuring", "Serious", "Sad", "Angry"];
const oldMouths = [[.06,0], [.40,.26], [.56,.29], [-.28,0], [.23,.06], [.34,.16], [-.74,-.74]];
async function flush() { for (let n = 0; n < 25; n++) await Promise.resolve(); }
function deferred() { let resolve; const promise = new Promise(done => { resolve = done; }); return {promise, resolve}; }
function point(x = 0, y = x) { return {x,y,set(a,b = a){this.x=a;this.y=b;}}; }
class Element extends EventEmitter {
  constructor() {
    super(); this.dataset={};this.children=[];this.isConnected=true;this.textContent="";
    const classes = new Set();
    this.classList={add:x=>classes.add(x),remove:x=>classes.delete(x),contains:x=>classes.has(x),
      toggle(x,on){if(on)classes.add(x);else classes.delete(x);}};
  }
  addEventListener(type, callback) { this.on(type, callback); }
  dispatchEvent(event) { this.emit(event.type, event); }
  appendChild(child) { this.children.push(child); child.parentElement=this; }
  getClientRects() { return [{}]; }
}
class Display {
  constructor(width=3840,height=5000) {
    this.naturalWidth=width;this.naturalHeight=height;
    this.scale=point(1);this.position=point();this.anchor=point();this.children=[];
  }
  get width() { return this.naturalWidth * this.scale.x; }
  get height() { return this.naturalHeight * this.scale.y; }
  addChild(child) { this.children.push(child);child.parent=this; }
  removeChild(child) { this.children=this.children.filter(item=>item!==child);child.parent=null; }
  destroy() { this.parent?.removeChild(this); }
}
async function client({enabled=true} = {}) {
  const target=new Element(), room=new Element(), shell=new Element(), mood=new Element();
  target.clientWidth=393;target.clientHeight=873;
  room.dataset.room="bedroom";shell.dataset.view="home";
  const document=new Element();document.hidden=false;
  const elements={"avatar-container":target,"avatar-fallback":new Element(),"avatar-state":new Element(),"mood-line":mood};
  document.getElementById=id=>elements[id];
  document.querySelector=selector=>({".room":room,".shell":shell})[selector]||null;
  const profile={id:"next",label:"Jade r21",available:true,manifestUrl:"/models/next/Jade.model3.json",
    presentation:"full",classicIntents:false,idleMotion:"Idle"};
  let now=0,variant=0,draws=0,timerId=0;
  const timers=new Map(),models=[],warnings=[];
  class Application {
    constructor(){this.view=new Element();this.stage=new Display();this.renderer={resize(){}};
      this.ticker={running:false,start(){this.running=true;},stop(){this.running=false;},add(){}};}
  }
  const window=new Element();
  Object.assign(window,{PIXI:{Application,Container:Display,UPDATE_PRIORITY:{LOW:-50},live2d:{MotionPriority:{IDLE:1}}},
    Live2DCubismCore:{},devicePixelRatio:1,
    JadeModelCatalog:{defaultId:"next",ready:Promise.resolve([profile]),get:id=>id==="next"?profile:null},
    JadeAvatarModelLoader:{async load(selected) {
      assert.equal(selected.id,"next","this campaign must never load r20");
      const model=new Display(),values=new Map();
      model.motions=[];model.loads=[];model.blink=1;model.values=values;
      const core={getDrawableRenderOrders:()=>[0],getParameterValueById:id=>values.get(id)??0,
        setParameterValueById(id,value,weight=1){values.set(id,(values.get(id)??0)*(1-weight)+value*weight);},
        addParameterValueById(id,value,weight=1){values.set(id,(values.get(id)??0)+value*weight);},
        multiplyParameterValueById(id,value,weight=1){values.set(id,(values.get(id)??0)*(1+(value-1)*weight));}};
      model.internalModel=Object.assign(new EventEmitter(),{coreModel:core,
        eyeBlink:{updateParameters(){values.set("ParamEyeLOpen",model.blink);values.set("ParamEyeROpen",model.blink);}},
        motionManager:Object.assign(new EventEmitter(),{loadMotion(group,index){
          model.loads.push([group,index]);
          return Promise.resolve(manifest.FileReferences.Motions[group]?.[index]||null);
        }})});
      model.motion=(group,index,priority)=>{model.motions.push({group,index,priority});return Promise.resolve();};
      model.frame=(inputs={})=>{
        values.clear();values.set("ParamBreath",.43);
        for(const [id,value] of Object.entries(inputs))values.set(id,value);
        model.internalModel.emit("beforeMotionUpdate");
        model.internalModel.emit("afterMotionUpdate");
        model.internalModel.emit("beforeModelUpdate");
        return Object.fromEntries(values);
      };
      models.push(model);return {model,dispose:()=>model.destroy()};
    }}});
  const context={window,document,Event:class {constructor(type){this.type=type;}},
    console:{warn:(...args)=>warnings.push(args)},
    fetch:async()=>({ok:true,json:async()=>({...palette,enabled})}),
    ResizeObserver:class {observe(){}},IntersectionObserver:class {observe(){}},
    performance:{now:()=>now},Math:Object.assign(Object.create(Math),{random(){draws++;return variant? .8:.2;}}),
    setTimeout(callback,delay){const id=++timerId;timers.set(id,{callback,delay});return id;},
    clearTimeout:id=>timers.delete(id)};
  vm.runInNewContext(source,context,{filename:"avatar.js"});await flush();
  assert.equal(window.JadeAvatar.state.status,"ready",JSON.stringify(warnings));
  return {avatar:window.JadeAvatar,model:models[0],models,room,shell,target,mood,
    advance(ms){now+=ms;},variant(value){variant=value;},get draws(){return draws;},
    run(delay){for(const [id,timer] of [...timers])if(timer.delay===delay){timers.delete(id);timer.callback();}},
    hide(value){document.hidden=value;document.emit("visibilitychange");}};
}

(async()=>{
  const session=await client();const {avatar,model}=session;
  assert.equal(session.models.length,1);
  assert.deepEqual(Object.keys(palette.intents),groups.map(group=>group.toLowerCase()));
  const signatures=new Map();
  for(const [g,group] of groups.entries()) {
    const files=manifest.FileReferences.Motions[group];
    assert.equal(files?.length,2,`${group}: the served r21 manifest must provide A and B`);
    for(const file of files)assert(fs.existsSync(path.join(bundle,file.File)),`${group}: missing exported motion`);
    for(let variant=0;variant<2;variant++) {
      session.variant(variant);avatar.setMouth(0);
      const before=model.motions.length;
      assert.equal(avatar.setIntent(group.toLowerCase(),{deferMotion:true}),true);
      session.advance(200);const pose=model.frame();
      assert.equal(model.motions.length,before,"the face prepares before the playback event");
      avatar.startReplyMotion(200);session.run(200);await flush();
      assert.deepEqual(model.motions.at(-1),{group,index:variant,priority:3});
      avatar.setSpeaking(true);avatar.setMouth(.67);const speaking=model.frame();
      assert(Math.abs(speaking.ParamMouthOpenY-.67)<1e-9,`${group}: speech drives the mouth`);
      model.blink=0;const closed=model.frame();
      assert.equal(closed.ParamEyeLOpen,0);assert.equal(closed.ParamEyeROpen,0);
      assert(Math.abs(closed.ParamMouthOpenY-.67)<1e-9,"blinking does not interrupt articulation");
      model.blink=1;avatar.setMouth(1);const vowel=model.frame();
      if(g<7) {
        assert.equal(pose.ParamMouthForm,oldMouths[g][0],`${group}: preserve the validated closed-mouth pose`);
        assert(Math.abs(vowel.ParamMouthForm-oldMouths[g][1])<1e-9,`${group}: preserve spoken mouth form`);
      }
      signatures.set(`${group}${variant}`,JSON.stringify([pose.ParamMouthForm,pose.ParamBrowLAngle,
        pose.ParamBrowRAngle,pose.ParamEyeLOpen,pose.ParamEyeROpen,pose.ParamEyeBallX,
        pose.ParamEyeBallY,pose.ParamBodyAngleX,pose.ParamBodyAngleZ]));
      avatar.setSpeaking(false);avatar.setMouth(0);avatar.finishReply(true);
      session.advance(450);const pause=model.frame();
      assert.equal(pause.ParamMouthForm,pose.ParamMouthForm,`${group}: the audio gap keeps its expression`);
      avatar.setSpeaking(true);avatar.startReplyMotion();session.run(600);await flush();
      assert.equal(model.motions.length,before+1,`${group}: a new PCM fragment must not replay the gesture`);
      avatar.setSpeaking(false);avatar.finishReply(true);session.advance(600);session.run(600);
      session.advance(220);session.run(220);
      const idle=model.frame();
      assert.equal(idle.ParamMouthOpenY,0);
      assert.equal(idle.ParamMouthForm,undefined,"the finished face releases its held shape");
      assert.equal(idle.ParamEyeLOpen,1);assert.equal(idle.ParamEyeROpen,1);
    }
  }
  assert.equal(session.draws,18,"one A/B choice per response, never per audio fragment");
  assert.equal(new Set(signatures.values()).size,18,"all A/B faces have distinct acting values");
  const earPoses=[];
  const originalEarAccents=[
    [360,.13,.10], [240,.40,-.10], [310,.53,.48], [610,.48,-.23],
    [1200,-.26,-.23], [950,.24,.22], [630,-.37,-.34],
  ];
  session.variant(0);
  for(const [i,intent] of groups.map(group=>group.toLowerCase()).entries()) {
    avatar.setIntent(intent,{deferMotion:true});session.advance(originalEarAccents[i]?.[0]??1350);
    const pose=model.frame(),ears=[pose.ParamJadeEarFollowL,pose.ParamJadeEarFollowR];
    earPoses.push(ears);
    if(i<7)ears.forEach((value,side)=>assert(Math.abs(value-originalEarAccents[i][side+1])<1e-9,
      `${intent}: preserve the previously validated ear accent`));
  }
  assert.equal(new Set(earPoses.map(value=>JSON.stringify(value))).size,9,"each intention retains its own ear attitude");
  assert(earPoses[7].every(value=>value<-.4),"sad ears droop into a sustained low pose");

  // All scene layouts keep the r21 loaded; the emotion is independent of framing.
  for(const room of ["bedroom","kitchen","living"])for(const [view,width,height,full] of
      [["home",393,650,false],["profile",393,220,false],["home",393,873,true]]) {
    session.room.dataset.room=room;session.shell.dataset.view=view;
    session.shell.classList.toggle("is-room-only",full);
    session.target.clientWidth=width;session.target.clientHeight=height;avatar.resize();
    avatar.setIntent("angry",{deferMotion:true});session.advance(200);
    assert(model.frame().ParamBrowLY<-.3,`${room}/${view}: the angry pose survives resizing`);
    assert.equal(avatar.state.modelId,"next");assert.equal(session.models.length,1);
  }

  // Cancellation and rapid replacement must also invalidate downloaded clips.
  const stale=deferred(),current=deferred();
  model.internalModel.motionManager.loadMotion=group=>group==="Sad"?stale.promise:current.promise;
  const before=model.motions.length;
  avatar.setIntent("sad",{deferMotion:true});avatar.startReplyMotion();avatar.resetIntent();
  avatar.setIntent("angry",{deferMotion:true});avatar.startReplyMotion();
  stale.resolve({});await flush();assert.equal(model.motions.length,before);
  current.resolve({});await flush();assert.equal(model.motions.at(-1).group,"Angry");
  assert.equal(model.motions.length,before+1);
  avatar.setSpeaking(false);avatar.setMouth(0);avatar.finishReply(false);
  session.advance(1500);session.run(1500);
  avatar.setIntent("curious",{deferMotion:true});session.advance(200);session.run(220);
  assert(model.frame().ParamBrowLY>.1,"an obsolete fade cannot erase the next reply");
  avatar.resetIntent();session.hide(true);session.run(600);session.run(220);session.hide(false);
  assert.equal(model.frame().ParamMouthForm,undefined,"background cancellation resumes at rest");

  // The face stays usable if its optional motion fails to download.
  model.internalModel.motionManager.loadMotion=()=>Promise.reject(new Error("offline motion"));
  avatar.setIntent("sad");session.advance(200);await flush();
  assert.equal(model.frame().ParamMouthForm,-1);
  avatar.resetIntent();avatar.setIntent("actually_unknown",{deferMotion:true});session.advance(200);
  assert.equal(model.frame().ParamMouthForm,.06,"an unknown intention falls back to neutral");
  avatar.resetIntent();

  const disabled=await client({enabled:false});
  for(const intent of groups.map(group=>group.toLowerCase()))disabled.avatar.setIntent(intent);
  await flush();
  assert.equal(disabled.model.motions.length,1,"visuals OFF leaves only Idle");
  disabled.avatar.setMouth(.55);
  assert.equal(disabled.model.frame().ParamMouthOpenY,.55,"visuals OFF still articulates played audio");
  assert.equal(disabled.draws,0);
  console.log("r21 intentions: 9 intentions / 18 variants; held poses, blink, lip-sync, PCM gaps, layouts, cancellation, missing clips and OFF passed");
})().catch(error=>{console.error(error);process.exitCode=1;});
