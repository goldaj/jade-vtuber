/* Headless contracts for the hybrid, non-invasive bedroom feature. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync("src/jade_runtime/mobile_web/seated-scene.js", "utf8");

async function test(available) {
  const room = {dataset:{room:"bedroom"}, events:[],
    addEventListener(){},
    dispatchEvent(event){this.events.push(event.type);} };
  const backdrop = {src:""}, body = {src:""};
  const requests = [], calls = [];
  class ImageMock {
    constructor(){this.naturalWidth=0;this.naturalHeight=0;}
    set src(value){
      this._src=value; requests.push(value);
      queueMicrotask(() => {
        if (available) {
          this.naturalWidth=value.includes("seated-body") ? 670 : 864;
          this.naturalHeight=value.includes("seated-body") ? 940 : 1536;
          this.onload();
        } else this.onerror();
      });
    }
    get src(){return this._src;}
  }
  const context={
    Image:ImageMock, Promise, Event:class {constructor(type){this.type=type;}},
    document:{
      querySelector(name){return name===".room" ? room : null;},
      getElementById(id){return id==="portrait-bedroom" ? backdrop :
        id==="portrait-seated-body" ? body : null;}
    },
    window:{JadeAvatar:{ready:true,canComposeSeated:true,
      prepareSeatedComposition(image){calls.push("compose");return image.naturalWidth===670;},
      resize(){calls.push("resize");}}}
  };
  vm.runInNewContext(source, context);
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(requests.length, 2);
  if (available) {
    assert.equal(room.dataset.seatedReady,"true");
    assert.equal(room.dataset.seatedCompositor,"true");
    assert.equal(room.events.length,1);
    assert.deepEqual(calls,["compose","resize"]);
    assert.equal(backdrop.src,"/assets/room-bedroom-portrait.avif");
    assert.equal(body.src,"/assets/jade-seated-body.avif");
  } else {
    assert.equal(room.dataset.seatedReady,"false");
    assert.deepEqual(calls,[]);
    assert.equal(backdrop.src,"");
    assert.equal(body.src,"");
  }
}

(async () => {
  await test(true);
  await test(false);
  console.log("Seated Jade: atomic paired-asset fallback and shared scene ready");
})().catch(error => {console.error(error); process.exitCode=1;});
