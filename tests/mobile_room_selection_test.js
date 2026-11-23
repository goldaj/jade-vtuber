/* Both rooms own independent, lifecycle-aware visual layers. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../src/jade_runtime/mobile_web/room-motion.js"), "utf8");
const html = fs.readFileSync(path.join(__dirname, "../src/jade_runtime/mobile_web/salon.html"), "utf8");
const css = fs.readFileSync(path.join(__dirname, "../src/jade_runtime/mobile_web/styles.css"), "utf8");

async function run(startRoom = "bedroom", supportsLayers = true) {
  const events = {}, mediaHandlers = {};
  const layers = Object.fromEntries(["curtain", "left", "right", "steam", "reflection"].map(x =>
    [x, {hidden:true, style:{transform:"", opacity:""}, src:""}]));
  layers.kitchen={hidden:true,style:{transform:"",opacity:""},src:""};
  const backdrop = {
    src:"/assets/room-spring.webp",
    getAttribute(name){return name === "src" ? this.src : null;},
  };
  const selectors = {
    ".room-plane > img":backdrop, ".room-curtain":layers.curtain,
    ".room-shadow-left":layers.left, ".room-shadow-right":layers.right,
    ".room-steam":layers.steam, ".room-reflection":layers.reflection,
    ".kitchen-effects":layers.kitchen,
  };
  const scene = {
    dataset:{}, attributes:{}, querySelector(q){return selectors[q];},
    toggleAttribute(n, flag){this.attributes[n] = flag;},
  };
  const room = {
    dataset:{room:"bedroom"},
    addEventListener(name,fn){events["room:"+name]=fn;},
    dispatchEvent(event){events["room:"+event.type]?.(event);}
  };
  const chooser = {
    value:"bedroom",
    addEventListener(name, fn){events["choose:"+name] = fn;},
  };
  const document = {
    hidden:false,
    querySelector(q){return q === ".room-art" ? scene : q === ".room" ? room : null;},
    getElementById(id){return id === "room-selector" ? chooser : null;},
    addEventListener(n, fn){events[n] = fn;},
  };
  let frameId = 0, cancelled = 0, onIntersection;
  const frames = new Set();
  class Image {
    constructor(){this.src="";this.naturalWidth=1448;this.naturalHeight=1086;}
    async decode(){return;}
  }
  const location = new URL("https://jade.local/?room=" + startRoom);
  const media = {matches:false, addEventListener(n, fn){mediaHandlers[n]=fn;}};
  const window = {
    location,
    history:{state:null,replaceState(_a,_b,route){const next=new URL(route,location);location.href=next.href;}},
  };
  const context = {
    document,window,Image,URL,URLSearchParams,
    Event:class {constructor(type){this.type=type;}},
    matchMedia:()=>media,
    CSS:{supports:()=>supportsLayers},
    requestAnimationFrame(){const id=++frameId;frames.add(id);return id;},
    cancelAnimationFrame(id){cancelled++;frames.delete(id);},
    IntersectionObserver:class{constructor(fn){onIntersection=fn;}observe(){}},
  };
  window.CSS=context.CSS;
  vm.runInNewContext(source,context,{filename:"room-motion.js"});
  for (let i=0;i<6;i++) await Promise.resolve();
  return {layers,backdrop,scene,room,chooser,events,media,mediaHandlers,window,frames,document,
    intersection(visible){onIntersection([{isIntersecting:visible}]);},
    get cancelled(){return cancelled;},
    async change(room) {
      chooser.value=room;
      events["choose:change"]();
      for (let i=0;i<6;i++) await Promise.resolve();
    }};
}

(async () => {
  const a=await run();
  assert.equal(a.backdrop.src,"/assets/room-backdrop.webp");
  assert.equal(a.scene.dataset.room,"bedroom");
  for (const key of ["curtain","left","right","steam","reflection"]) assert.equal(a.layers[key].hidden,false);
  assert.equal(a.layers.kitchen.hidden,true,"kitchen stays inactive in bedroom");
  assert.equal(a.frames.size,1,"bedroom starts exactly one render loop");
  a.room.dataset.seatedReady="true";
  a.room.dispatchEvent({type:"jade-seated-ready"});
  assert.equal(a.frames.size,0,"seated portrait disables old 4:3 room motion");
  assert.equal(a.layers.curtain.hidden,true,"no old curtain over portrait room");
  a.room.dataset.seatedReady="false";
  a.room.dispatchEvent({type:"jade-seated-ready"});
  assert.equal(a.frames.size,1,"old bedroom layers resume in a real fallback");
  await a.change("kitchen");
  assert.equal(a.backdrop.src,"/assets/room-kitchen.webp");
  assert.equal(a.scene.dataset.room,"kitchen");
  assert.equal(a.frames.size,0,"bedroom loop cancelled on kitchen entry");
  assert.ok(a.cancelled>=1);
  for (const key of ["curtain","left","right","steam","reflection"]) assert.equal(a.layers[key].hidden,true);
  assert.equal(a.layers.kitchen.hidden,false,"kitchen effects enabled on kitchen");
  assert.equal(a.scene.attributes["data-paused"],false);
  a.document.hidden=true;
  a.events.visibilitychange();
  assert.equal(a.scene.attributes["data-paused"],true,"kitchen CSS effects pause in hidden tabs");
  a.document.hidden=false;
  a.events.visibilitychange();
  assert.equal(a.scene.attributes["data-paused"],false,"kitchen resumes in visible tab");
  a.intersection(false);
  assert.equal(a.scene.attributes["data-paused"],true,"kitchen stops out of viewport");
  a.intersection(true);
  assert.equal(a.scene.attributes["data-paused"],false);
  assert.equal(a.window.location.search,"?room=kitchen");
  await a.change("bedroom");
  assert.equal(a.backdrop.src,"/assets/room-backdrop.webp");
  for (const key of ["curtain","left","right","steam","reflection"]) assert.equal(a.layers[key].hidden,false);
  assert.equal(a.layers.kitchen.hidden,true,"kitchen effects hidden on return");
  assert.equal(a.frames.size,1,"bedroom animation resumes on return");
  assert.equal(a.window.location.search,"");
  a.media.matches=true;
  a.mediaHandlers.change();
  assert.equal(a.backdrop.src,"/assets/room-spring.webp","reduced motion keeps static bedroom");
  assert.equal(a.frames.size,0);
  for (const layer of Object.values(a.layers)) assert.equal(layer.hidden,true);

  const b=await run("kitchen");
  assert.equal(b.backdrop.src,"/assets/room-kitchen.webp");
  for (const key of ["curtain","left","right","steam","reflection"]) assert.equal(b.layers[key].hidden,true);
  assert.equal(b.layers.kitchen.hidden,false);
  assert.equal(b.frames.size,0,"kitchen runs no bedroom rAF loop");
  b.media.matches=true;
  b.mediaHandlers.change();
  assert.equal(b.layers.kitchen.hidden,true,"reduced-motion disables kitchen effects");
  b.media.matches=false;
  b.mediaHandlers.change();
  assert.equal(b.layers.kitchen.hidden,false);
  await b.change("bedroom");
  assert.equal(b.frames.size,1);
  assert.equal(b.layers.kitchen.hidden,true);

  const c=await run("bedroom",false);
  assert.equal(c.backdrop.src,"/assets/room-spring.webp");
  await c.change("kitchen");
  assert.equal(c.backdrop.src,"/assets/room-kitchen.webp","switch still works without cqh support");
  assert.equal(c.frames.size,0);
  assert.equal(c.layers.kitchen.hidden,true,"unsupported cqh yields static kitchen");
  assert.match(html,/class="kitchen-effects" hidden/);
  assert.equal((html.match(/class="kitchen-vine kitchen-vine-/g)||[]).length,3);
  assert.match(html,/class="kitchen-steam"/);
  assert.match(css,/\.kitchen-sunlight::before/);
  assert.match(css,/\.room-art\[data-paused\] \.kitchen-wisp/);
  assert.match(css,/\.kitchen-effects\[hidden\]\{display:none!important\}/);
  process.stdout.write("Bedroom/Kitchen scene isolation and effects: PASS\n");
})().catch(e=>{console.error(e);process.exitCode=1;});
