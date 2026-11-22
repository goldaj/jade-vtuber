/* Room scene switching: static kitchen never inherits bedroom animation. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../src/jade_runtime/mobile_web/room-motion.js"), "utf8");

async function run(startRoom = "bedroom", supportsLayers = true) {
  const events = {}, mediaHandlers = {};
  const layers = Object.fromEntries(["curtain", "left", "right", "steam", "reflection"].map(x =>
    [x, {hidden:true, style:{transform:"", opacity:""}, src:""}]));
  const backdrop = {
    src:"/assets/room-spring.webp",
    getAttribute(name){return name === "src" ? this.src : null;},
  };
  const selectors = {
    ".room-plane > img":backdrop, ".room-curtain":layers.curtain,
    ".room-shadow-left":layers.left, ".room-shadow-right":layers.right,
    ".room-steam":layers.steam, ".room-reflection":layers.reflection,
  };
  const scene = {
    dataset:{}, attributes:{}, querySelector(q){return selectors[q];},
    toggleAttribute(n, flag){this.attributes[n] = flag;},
  };
  const chooser = {
    value:"bedroom",
    addEventListener(name, fn){events["choose:"+name] = fn;},
  };
  const document = {
    hidden:false,
    querySelector(q){return q === ".room-art" ? scene : null;},
    getElementById(id){return id === "room-selector" ? chooser : null;},
    addEventListener(n, fn){events[n] = fn;},
  };
  let frameId = 0, cancelled = 0;
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
    document,window,Image,URL,URLSearchParams,matchMedia:()=>media,
    CSS:{supports:()=>supportsLayers},
    requestAnimationFrame(){const id=++frameId;frames.add(id);return id;},
    cancelAnimationFrame(id){cancelled++;frames.delete(id);},
    IntersectionObserver:class{constructor(fn){this.fn=fn;}observe(){}},
  };
  window.CSS=context.CSS;
  vm.runInNewContext(source,context,{filename:"room-motion.js"});
  for (let i=0;i<6;i++) await Promise.resolve();
  return {layers,backdrop,scene,chooser,events,media,mediaHandlers,window,frames,
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
  for (const layer of Object.values(a.layers)) assert.equal(layer.hidden,false);
  assert.equal(a.frames.size,1,"bedroom starts exactly one render loop");
  await a.change("kitchen");
  assert.equal(a.backdrop.src,"/assets/room-kitchen.webp");
  assert.equal(a.scene.dataset.room,"kitchen");
  assert.equal(a.frames.size,0,"bedroom loop cancelled on kitchen entry");
  assert.ok(a.cancelled>=1);
  for (const layer of Object.values(a.layers)) assert.equal(layer.hidden,true);
  assert.equal(a.window.location.search,"?room=kitchen");
  await a.change("bedroom");
  assert.equal(a.backdrop.src,"/assets/room-backdrop.webp");
  for (const layer of Object.values(a.layers)) assert.equal(layer.hidden,false);
  assert.equal(a.frames.size,1,"bedroom animation resumes on return");
  assert.equal(a.window.location.search,"");
  a.media.matches=true;
  a.mediaHandlers.change();
  assert.equal(a.backdrop.src,"/assets/room-spring.webp","reduced motion keeps static bedroom");
  assert.equal(a.frames.size,0);
  for (const layer of Object.values(a.layers)) assert.equal(layer.hidden,true);

  const b=await run("kitchen");
  assert.equal(b.backdrop.src,"/assets/room-kitchen.webp");
  for (const layer of Object.values(b.layers)) assert.equal(layer.hidden,true);
  await b.change("bedroom");
  assert.equal(b.frames.size,1);

  const c=await run("bedroom",false);
  assert.equal(c.backdrop.src,"/assets/room-spring.webp");
  await c.change("kitchen");
  assert.equal(c.backdrop.src,"/assets/room-kitchen.webp","switch still works without cqh support");
  assert.equal(c.frames.size,0);
  process.stdout.write("Bedroom/Kitchen scene isolation: PASS\n");
})().catch(e=>{console.error(e);process.exitCode=1;});
