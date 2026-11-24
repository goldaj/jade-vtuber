/* Headless contracts for the hybrid, non-invasive bedroom feature. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync("src/jade_runtime/mobile_web/seated-scene.js", "utf8");

async function test(available, composable = true, isolatable = true, bodyHeight = 940, bodyWidth = 670) {
  const room = {dataset:{room:"bedroom"}, events:[],
    addEventListener(){},
    dispatchEvent(event){this.events.push(event.type);} };
  const properties = {};
  const backdrop = {src:""}, body = {src:"",style:{setProperty(name,value){properties[name]=value;}}};
  const requests = [], calls = [];
  class ImageMock {
    constructor(){this.naturalWidth=0;this.naturalHeight=0;}
    set src(value){
      this._src=value; requests.push(value);
      queueMicrotask(() => {
        if (available) {
          this.naturalWidth=value.includes("seated-body") ? bodyWidth : 864;
          this.naturalHeight=value.includes("seated-body") ? bodyHeight : 1536;
          this.onload();
        } else this.onerror();
      });
    }
    get src(){return this._src;}
  }
  const context={
    console:{warn(){}}, Image:ImageMock, Promise, Event:class {constructor(type){this.type=type;}},
    document:{
      querySelector(name){return name===".room" ? room : null;},
      getElementById(id){return id==="portrait-bedroom" ? backdrop :
        id==="portrait-seated-body" ? body : null;}
    },
    window:{JadeAvatar:{ready:true,canIsolateHead:isolatable,canComposeSeated:composable,
      prepareSeatedComposition(image){calls.push("compose");return image.naturalWidth===670;},
      resize(){calls.push("resize");}}}
  };
  vm.runInNewContext(source, context);
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(requests.length, 2);
  if (available && isolatable && bodyWidth === 670 && [940, 956].includes(bodyHeight)) {
    assert.equal(room.dataset.seatedReady,"true");
    assert.equal(room.dataset.seatedCompositor,composable?"true":"false");
    assert.equal(room.events.length,1);
    assert.deepEqual(calls,composable?["compose","resize"]:["resize"]);
    assert.equal(backdrop.src,"/assets/room-bedroom-portrait.avif");
    assert.equal(body.src,"/assets/jade-seated-body.avif");
    const {top,height} = context.window.JadeSeatedScene.layout;
    assert.ok(Math.abs(top + height - (.406699 + .562201)) < 1e-12);
    assert.ok(Math.abs(height / bodyHeight - .562201 / 940) < 1e-12);
    assert.ok(Math.abs(top + height * (bodyHeight - 940) / bodyHeight - .406699) < 1e-12);
    assert.ok(Math.abs(parseFloat(properties["--seated-body-top"]) / 100 - top) < 1e-12);
    assert.ok(Math.abs(parseFloat(properties["--seated-body-height"]) / 100 - height) < 1e-12);
  } else {
    assert.notEqual(room.dataset.seatedReady,"true");
    assert.deepEqual(calls,[]);
    assert.equal(backdrop.src,"");
    assert.equal(body.src,"");
  }
}

(async () => {
  await test(true);
  await test(true,false); // Renderer split unavailable: the seated body must stay.
  await test(true,true,false); // Cannot isolate the standing body: no hybrid.
  await test(true,true,true,956);
  await test(true,false,true,956);
  await test(true,true,true,955); // unrelated crop rejected
  await test(true,true,true,956,671); // incorrect width rejected
  await test(false);
  console.log("Seated Jade: atomic paired-asset fallback and shared scene ready");
})().catch(error => {console.error(error); process.exitCode=1;});
