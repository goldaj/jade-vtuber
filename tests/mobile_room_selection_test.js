/* Room selection, delayed kitchen loading and lifecycle-aware kitchen accents. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const web = path.join(__dirname, "../src/jade_runtime/mobile_web");
const source = fs.readFileSync(path.join(web, "room-motion.js"), "utf8");
const html = fs.readFileSync(path.join(web, "salon.html"), "utf8");
const css = fs.readFileSync(path.join(web, "styles.css"), "utf8");
const settle = () => new Promise(resolve => setImmediate(resolve));

async function run({startRoom = "bedroom", supportsEffects = true, manual = false} = {}) {
  const events = {}, mediaHandlers = {}, requests = [], roomEvents = [];
  const kitchenImage = {src:""}, kitchenEffects = {hidden:true};
  const scene = {
    attributes:{},
    querySelector(q){return q === ".room-plane > img" ? kitchenImage : kitchenEffects;},
    toggleAttribute(name, enabled){this.attributes[name] = enabled;},
  };
  const room = {dataset:{room:"bedroom"}, dispatchEvent(event){roomEvents.push(event.type);}};
  const chooser = {value:"bedroom", addEventListener(name, fn){events["choose:"+name] = fn;}};
  const document = {
    hidden:false,
    querySelector(q){return q === ".room-art" ? scene : q === ".room" ? room : null;},
    getElementById(id){return id === "room-selector" ? chooser : null;},
    addEventListener(name, fn){events[name] = fn;},
  };
  let onIntersection;
  class Image {
    constructor(){this.src="";this.naturalWidth=1448;this.naturalHeight=1086;}
    decode(){
      return new Promise((resolve, reject) => {
        requests.push({src:this.src, resolve, reject});
        if(!manual) resolve();
      });
    }
  }
  const location = new URL("https://jade.local/?room=" + startRoom);
  const media = {matches:false, addEventListener(name, fn){mediaHandlers[name] = fn;}};
  const window = {location, history:{state:null,replaceState(_a,_b,route){location.href = new URL(route,location).href;}}};
  vm.runInNewContext(source,{
    document,window,Image,URL,URLSearchParams,
    Event:class {constructor(type){this.type=type;}},
    matchMedia:()=>media,
    CSS:{supports:()=>supportsEffects},
    IntersectionObserver:class{constructor(fn){onIntersection=fn;}observe(target){assert.equal(target,scene);}},
  },{filename:"room-motion.js"});
  await settle();
  return {kitchenImage,kitchenEffects,scene,room,chooser,events,media,mediaHandlers,window,document,requests,roomEvents,
    intersection(visible){onIntersection([{isIntersecting:visible}]);},
    async change(next){chooser.value=next;events["choose:change"]();await settle();}};
}

(async () => {
  assert.match(html, /id="portrait-bedroom"[^>]*src="\/assets\/room-bedroom-portrait\.avif"/);
  assert.equal((html.match(/id="portrait-bedroom"/g)||[]).length,1);
  assert.doesNotMatch(html + source + css,/room-(?:spring|backdrop|curtain)\.webp/);
  const a=await run();
  assert.equal(a.room.dataset.room,"bedroom");
  assert.equal(a.requests.length,0,"bedroom needs no script-selected replacement");
  assert.equal(a.kitchenEffects.hidden,true);
  assert.equal(a.scene.attributes["data-paused"],true);

  await a.change("kitchen");
  assert.equal(a.kitchenImage.src,"/assets/room-kitchen.webp");
  assert.equal(a.room.dataset.room,"kitchen");
  assert.equal(a.kitchenEffects.hidden,false);
  assert.equal(a.scene.attributes["data-paused"],false);
  assert.equal(a.window.location.search,"?room=kitchen");
  a.document.hidden=true;
  a.events.visibilitychange();
  assert.equal(a.scene.attributes["data-paused"],true,"hidden page pauses kitchen effects");
  a.document.hidden=false;
  a.events.visibilitychange();
  assert.equal(a.scene.attributes["data-paused"],false);
  a.intersection(false);
  assert.equal(a.scene.attributes["data-paused"],true,"offscreen kitchen pauses decoration");
  a.intersection(true);
  assert.equal(a.scene.attributes["data-paused"],false);
  a.media.matches=true;
  a.mediaHandlers.change();
  assert.equal(a.kitchenEffects.hidden,true,"reduced motion keeps the kitchen static");
  a.media.matches=false;
  a.mediaHandlers.change();
  await a.change("bedroom");
  assert.equal(a.room.dataset.room,"bedroom");
  assert.equal(a.kitchenEffects.hidden,true,"kitchen effects are hidden on return");
  assert.equal(a.window.location.search,"");
  assert.deepEqual(a.roomEvents,["jade-room-changed","jade-room-changed"]);
  await a.change("kitchen");
  assert.equal(a.requests.length,1,"the same kitchen is reused");

  const b=await run({startRoom:"kitchen",supportsEffects:false});
  assert.equal(b.room.dataset.room,"kitchen","direct room links still work");
  assert.equal(b.kitchenImage.src,"/assets/room-kitchen.webp");
  assert.equal(b.kitchenEffects.hidden,true,"unsupported container units leave a static kitchen");

  const race=await run({manual:true});
  await race.change("kitchen");
  assert.equal(race.room.dataset.room,"bedroom","slow kitchen decode preserves the current portrait room");
  await race.change("bedroom");
  race.requests[0].resolve();
  await settle();
  assert.equal(race.room.dataset.room,"bedroom","a late kitchen image cannot replace a newer choice");

  const failed=await run({manual:true});
  await failed.change("kitchen");
  failed.requests[0].reject(new Error("offline"));
  await settle();
  assert.equal(failed.room.dataset.room,"bedroom");
  assert.equal(failed.chooser.value,"bedroom");
  await failed.change("kitchen");
  failed.requests[1].resolve();
  await settle();
  assert.equal(failed.room.dataset.room,"kitchen","a failed image can be retried");

  assert.match(html,/class="kitchen-effects" hidden/);
  assert.equal((html.match(/class="kitchen-vine kitchen-vine-/g)||[]).length,3);
  assert.match(html,/class="kitchen-steam"/);
  assert.match(css,/\.kitchen-sunlight::before/);
  assert.match(css,/\.room-art\[data-paused\] \.kitchen-wisp/);
  assert.match(css,/\.kitchen-effects\[hidden\]\{display:none!important\}/);
  console.log("Room selection: canonical portrait, kitchen transitions, loading races and effects PASS");
})().catch(error=>{console.error(error);process.exitCode=1;});
