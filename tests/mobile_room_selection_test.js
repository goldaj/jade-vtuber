/* Room selection, independent static portrait loading and selection. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const web = path.join(__dirname, "../src/jade_runtime/mobile_web");
const source = fs.readFileSync(path.join(web, "room-motion.js"), "utf8");
const preferencesSource = fs.readFileSync(path.join(web, "preferences.js"), "utf8");
const html = fs.readFileSync(path.join(web, "salon.html"), "utf8");
const css = ["styles.css", "jade-theme.css"].map(name => fs.readFileSync(path.join(web, name), "utf8")).join("\n");
const settle = () => new Promise(resolve => setImmediate(resolve));

async function run({startRoom = null, manual = false, storage = new Map()} = {}) {
  const events = {}, requests = [], roomEvents = [];
  const staticImage = {src:""};
  const scene = {querySelector(q){return q === ".room-plane > img" ? staticImage : null;}};
  const room = {dataset:{room:"bedroom"}, dispatchEvent(event){roomEvents.push(event.type);}};
  const chooser = {value:"bedroom", addEventListener(name, fn){events["choose:"+name] = fn;}};
  const document = {
    hidden:false,
    querySelector(q){return q === ".room-art" ? scene : q === ".room" ? room : null;},
    getElementById(id){return id === "room-selector" ? chooser : null;},
    addEventListener(name, fn){events[name] = fn;},
  };
  class Image {
    constructor(){this.src="";this.naturalWidth=941;this.naturalHeight=1672;}
    decode(){
      return new Promise((resolve, reject) => {
        requests.push({src:this.src, resolve, reject});
        if(!manual) resolve();
      });
    }
  }
  const location = new URL("https://jade.local/" + (startRoom === null ? "" : "?room=" + startRoom));
  const window = {location, history:{state:null,replaceState(_a,_b,route){location.href = new URL(route,location).href;}},
    localStorage:{getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value)}};
  const context = vm.createContext({
    document,window,Image,URL,URLSearchParams,
    Event:class {constructor(type){this.type=type;}},
  });
  vm.runInContext(preferencesSource,context,{filename:"preferences.js"});
  vm.runInContext(source,context,{filename:"room-motion.js"});
  await settle();
  return {staticImage,room,chooser,events,window,document,requests,roomEvents,storage,
    async change(next){chooser.value=next;events["choose:change"]();await settle();}};
}

(async () => {
  assert.match(html, /id="portrait-bedroom"[^>]*src="\/assets\/room-bedroom-portrait\.avif"/);
  assert.equal((html.match(/id="portrait-bedroom"/g)||[]).length,1);
  assert.doesNotMatch(html + source + css,/room-(?:spring|backdrop|curtain)\.webp/);
  const a=await run();
  assert.equal(a.room.dataset.room,"bedroom");
  assert.equal(a.requests.length,0,"bedroom needs no script-selected replacement");

  await a.change("kitchen");
  assert.equal(a.staticImage.src,"/assets/room-kitchen-portrait.avif");
  assert.equal(a.room.dataset.room,"kitchen");
  assert.equal(a.window.location.search,"?room=kitchen");
  await a.change("bedroom");
  assert.equal(a.room.dataset.room,"bedroom");
  assert.equal(a.window.location.search,"");
  assert.deepEqual(a.roomEvents,["jade-room-changed","jade-room-changed"]);
  await a.change("kitchen");
  assert.equal(a.requests.length,1,"the same kitchen is reused");
  const reopened=await run({storage:a.storage});
  assert.equal(reopened.room.dataset.room,"kitchen","a fresh app URL restores the selected room");
  const explicit=await run({storage:a.storage,startRoom:"bedroom"});
  assert.equal(explicit.room.dataset.room,"bedroom","an explicit supported URL choice overrides the saved room");
  assert.equal((await run({storage:a.storage})).room.dataset.room,"bedroom","the explicit room choice is saved");

  const b=await run({startRoom:"kitchen"});
  assert.equal(b.room.dataset.room,"kitchen","direct room links still work");
  assert.equal(b.staticImage.src,"/assets/room-kitchen-portrait.avif");

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
  assert.equal(failed.window.JadePreferences.get("room"),undefined,"a failed room image is never persisted as selected");
  await failed.change("kitchen");
  failed.requests[1].resolve();
  await settle();
  assert.equal(failed.room.dataset.room,"kitchen","a failed image can be retried");

  const living=await run({startRoom:"living"});
  assert.equal(living.room.dataset.room,"living","direct salon link works");
  assert.equal(living.staticImage.src,"/assets/room-living-portrait.avif");
  assert.equal(living.requests.length,1,"only the selected static room loads");
  await living.change("kitchen");
  assert.equal(living.room.dataset.room,"kitchen");
  assert.equal(living.staticImage.src,"/assets/room-kitchen-portrait.avif");
  await living.change("living");
  assert.equal(living.staticImage.src,"/assets/room-living-portrait.avif");
  assert.equal(living.requests.length,2,"both static rooms retain independent decoded sources");
  assert.equal((await run({storage:living.storage})).room.dataset.room,"living");
  const override=await run({storage:living.storage,startRoom:"kitchen"});
  assert.equal(override.room.dataset.room,"kitchen","URL overrides saved salon");
  await override.change("living");
  assert.equal(override.window.location.search,"?room=living");
  await override.change("bedroom");
  assert.equal(override.window.location.search,"");
  assert.equal((await run({storage:living.storage})).room.dataset.room,"bedroom");

  const crossed=await run({manual:true});
  await crossed.change("kitchen");
  await crossed.change("living");
  crossed.requests[1].resolve();
  await settle();
  assert.equal(crossed.room.dataset.room,"living");
  assert.equal(crossed.staticImage.src,"/assets/room-living-portrait.avif");
  crossed.requests[0].resolve();
  await settle();
  assert.equal(crossed.room.dataset.room,"living");
  assert.equal(crossed.staticImage.src,"/assets/room-living-portrait.avif","late kitchen decode must not replace salon");
  await crossed.change("kitchen");
  assert.equal(crossed.staticImage.src,"/assets/room-kitchen-portrait.avif");

  const rejected=await run({manual:true});
  await rejected.change("kitchen");
  rejected.requests[0].resolve();
  await settle();
  await rejected.change("living");
  rejected.requests[1].reject(new Error("offline"));
  await settle();
  assert.equal(rejected.room.dataset.room,"kitchen");
  assert.equal(rejected.chooser.value,"kitchen");
  assert.equal(rejected.staticImage.src,"/assets/room-kitchen-portrait.avif");
  assert.equal(rejected.window.JadePreferences.get("room"),"kitchen");
  await rejected.change("living");
  rejected.requests[2].resolve();
  await settle();
  assert.equal(rejected.room.dataset.room,"living","failed salon decode can retry");
  await rejected.change("invalid");
  assert.equal(rejected.room.dataset.room,"living");
  assert.equal(rejected.requests.length,3,"invalid room cannot request an asset");

  assert.match(html,/<option value="living">Salon<\/option>/);
  assert.match(html,/id="portrait-static-room" width="941" height="1672"/);
  assert.match(css,/\.room-plane,\.bedroom-frame\{/);
  assert.doesNotMatch(html + source + css,/kitchen-(?:effects|vine|steam|wisp|sunlight)|room-kitchen\.webp/);
  console.log("Room selection: all three rooms, persistence, independent assets, failures and loading races PASS");
})().catch(error=>{console.error(error);process.exitCode=1;});
