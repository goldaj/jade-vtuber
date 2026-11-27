/* Independent portrait effects: geometry, animation bounds and lifecycle. */
"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const path=require("node:path");
const script=path.join(__dirname,"../src/jade_runtime/mobile_web/portrait-bedroom-motion.js");
const preferences=fs.readFileSync(path.join(__dirname,"../src/jade_runtime/mobile_web/preferences.js"),"utf8");
const m=require(script);
assert.equal(m.W,864);assert.equal(m.H,1536);
for(const p of [...m.curtainRegions,...m.blossomRegions,...m.lightRegions,m.birdRegion]){
  for(const [x,y] of p){assert.ok(x>=0&&x<=m.W&&y>=0&&y<=m.H);assert.ok(m.maskAlpha(p,x,y)<1e-9);}
  const center=p.reduce((s,q)=>[s[0]+q[0]/p.length,s[1]+q[1]/p.length],[0,0]);
  assert.ok(m.inside(p,...center));assert.ok(m.maskAlpha(p,...center)>.5);
  assert.equal(m.maskAlpha(p,0,1535),0);
}
assert.ok(m.branchAlpha(87,180,245)<.1,"blue sky is excluded");
assert.ok(m.branchAlpha(250,242,213)>.9,"flowers extracted");
assert.ok(m.branchAlpha(91,71,43)>.9,"dark branch extracted");
assert.ok(m.lightAlpha(250,202,145)>.8);
assert.ok(m.lightAlpha(200,115,120)<.1,"pink ceiling base excluded");
assert.ok(m.fabricAlpha(231,184,175)>.8);
assert.ok(m.fabricAlpha(132,65,24)<.1,"dark wood excluded");
let lo=Infinity,hi=-Infinity;
for(let t=0;t<100;t+=.05){
  assert.equal(m.curtainOffset(308,t),0);
  const v=m.curtainOffset(800,t);lo=Math.min(lo,v);hi=Math.max(hi,v);
  assert.ok(Math.abs(v)<=23.1);
}
assert.ok(hi-lo>25,"visible curtain movement");
assert.ok(m.AMPLITUDE.lightX>=20&&m.AMPLITUDE.branchX>=10);
assert.equal(m.birdProgress(0),-1);assert.equal(m.birdProgress(1.5),0);
assert.equal(m.birdProgress(6.5),1);assert.equal(m.birdProgress(10),-1);
for(let n=0;n<32;n++){
  const flags=Array.from({length:5},(_,i)=>Boolean(n&(1<<i)));
  assert.equal(m.shouldRun(...flags),n===23);
}
// Exercise the actual browser lifecycle, with a deliberately unsupported
// image and a supported canvas mock. No GPU/DOM dependency in CI.
function boot(width=864, pixelFailure=false, complete=true, storage=new Map()) {
  const events={},frames=new Map();let id=0,intersection,draws=0,clears=0;
  function ctx(){return {
    drawImage(){draws++;},clearRect(){clears++;},fillRect(){},
    createImageData(w,h){return {data:new Uint8ClampedArray(w*h*4)};},
    getImageData(x,y,w,h){
      if(pixelFailure)throw Error("pixel read unavailable");
      const d=new Uint8ClampedArray(w*h*4);
      for(let i=0;i<d.length;i+=4){d[i]=220;d[i+1]=167;d[i+2]=160;d[i+3]=255;}
      return {data:d};
    },
    putImageData(){},beginPath(){},arc(){},fill(){},save(){},restore(){},
    createRadialGradient(){return {addColorStop(){}};},
    lineTo(){},moveTo(){},closePath(){},clip(){},quadraticCurveTo(){},stroke(){}
  };}
  function canvas(){const c=ctx();return {hidden:true,getContext(){return c;}};}
  const output=canvas(),room={dataset:{room:"bedroom"},
    addEventListener(n,fn){events[n]=fn;}};
  const backdrop={complete,naturalWidth:width,naturalHeight:1536,
    addEventListener(n,fn){events[n]=fn;}};
  const toggle={checked:true,addEventListener(n,fn){events.toggle=fn;}};
  const status={textContent:""};
  const doc={hidden:false,querySelector(){return room;},getElementById(id){
    return id==="portrait-bedroom"?backdrop:id==="portrait-bedroom-motion"?output:
      id==="portrait-motion-enabled"?toggle:id==="portrait-motion-status"?status:null;},createElement:canvas,
    addEventListener(n,fn){events[n]=fn;}};
  const media={matches:false,addEventListener(n,fn){events.media=fn;}};
  const window={localStorage:{getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value)}};
  const context=vm.createContext({
    window,
    document:doc,matchMedia:()=>media,console:{warn(){}},
    requestAnimationFrame(fn){frames.set(++id,fn);return id;},
    cancelAnimationFrame(n){frames.delete(n);},
    IntersectionObserver:class{constructor(fn){intersection=fn;}observe(target){assert.equal(target,room);}}
  });
  vm.runInContext(preferences,context);
  vm.runInContext(fs.readFileSync(script,"utf8"),context);
  return {output,room,doc,media,frames,events,backdrop,toggle,status,storage,get draws(){return draws;},get clears(){return clears;},
    step(t){const a=[...frames.values()];frames.clear();a.forEach(f=>f(t));},
    intersect(v){intersection([{isIntersecting:v}]);}};
}
const b=boot();
assert.equal(b.frames.size,1);assert.equal(b.output.hidden,false);
b.step(0);const c=b.clears;b.step(16);assert.equal(b.clears,c,"24fps limit");
b.step(44);assert.ok(b.clears>c);assert.ok(b.draws>0);
b.room.dataset.room="kitchen";b.events["jade-room-changed"]();
assert.equal(b.frames.size,0);assert.equal(b.output.hidden,true);
b.room.dataset.room="bedroom";b.events["jade-room-changed"]();assert.equal(b.frames.size,1);
b.doc.hidden=true;b.events.visibilitychange();assert.equal(b.frames.size,0);
b.doc.hidden=false;b.events.visibilitychange();assert.equal(b.frames.size,1);
b.intersect(false);assert.equal(b.frames.size,0);
b.intersect(true);assert.equal(b.frames.size,1);
b.media.matches=true;b.events.media();assert.equal(b.frames.size,1);
assert.equal(b.status.textContent,"");assert.equal(b.status.hidden,true);
b.media.matches=false;b.events.media();assert.equal(b.frames.size,1);
b.toggle.checked=false;b.events.toggle();assert.equal(b.frames.size,0);assert.equal(b.output.hidden,true);
const restored=boot(864,false,true,b.storage);
assert.equal(restored.toggle.checked,false,"animation setting survives a fresh page");
assert.equal(restored.frames.size,0,"saved disabled animations never start a frame on reopening");
b.toggle.checked=true;b.events.toggle();assert.equal(b.frames.size,1);
assert.equal(boot(864,false,true,b.storage).toggle.checked,true,"reenabling replaces the saved setting");
assert.equal(b.events["jade-seated-ready"],undefined,"bedroom does not listen to avatar readiness");
const pending=boot(0,false,false);
assert.equal(pending.frames.size,0);
assert.equal(pending.room.dataset.portraitMotion,"loading");
pending.backdrop.complete=true;pending.backdrop.naturalWidth=864;pending.events.load();
assert.equal(pending.frames.size,1,"portrait starts as soon as its own image loads");
const unavailable=boot(0);
assert.equal(unavailable.frames.size,0);
assert.equal(unavailable.room.dataset.portraitMotion,"unavailable");
const scaled=boot(865);assert.equal(scaled.frames.size,1,"same aspect ratio is accepted");
const unsupported=boot(1200);assert.equal(unsupported.frames.size,1);assert.equal(unsupported.room.dataset.portraitMotion,"partial");
const failed=boot(864,true);assert.equal(failed.frames.size,1);assert.equal(failed.room.dataset.portraitMotion,"partial");
failed.step(0);assert.equal(failed.frames.size,1,"ambient effects survive pixel failures");
console.log("Portrait bedroom motion: isolated geometry, amplitude, scheduling and lifecycle PASS");
