"use strict";
const assert = require("node:assert/strict");
const vm = require("node:vm");
const fs = require("node:fs");
const source = fs.readFileSync("src/jade_runtime/mobile_web/head-isolation.js", "utf8");
const HIDE = [
  "PartJAD_BODY","PartJAD_BODY_SKIN","PartJAD_ARM_L","PartJAD_ARM_R",
  "PartJAD_DRESS","PartJAD_DRESS_SLEEVE_L","PartJAD_DRESS_SLEEVE_R",
  "PartJAD_DRESS_SKIRT"
];
const ids = [
  "PartJAD_ROOT", "PartJAD_HAIR_BACK", "PartJAD_HAIR_BACK_L",
  "PartJAD_FACE", "PartJAD_HAIR_FRONT", ...HIDE
];
// Rear mesh is a child of the rear part; foreground hair remains foreground.
const partParents = [-1,0,1,0,0,0,5,5,5,5,5,5,5,5];
const drawableParents = [2,3,4,5,6]; // rear, face, front hair, body, skin
const opacity = new Float32Array([.7,.8,.9,1,.6]);
const initial = Array.from(opacity);
const calls = [];
const partOpacity = ids.map(() => 1);
// Actual Cubism Web Core property rather than an inaccurate test double.
const raw = {parts:{ids,count:ids.length,parentIndices:partParents},
  drawables:{count:opacity.length,parentPartIndices:drawableParents,opacities:opacity}};
const core = {
  getModel(){return raw;},
  getPartCount(){return ids.length;},
  setPartOpacityByIndex(i,v){calls.push([i,v]);partOpacity[i]=v;},
  getPartOpacityByIndex(i){return partOpacity[i];}
};
const window = {};
vm.runInNewContext(source, {window});
const controller = window.JadeHeadIsolation.forModel(core);
assert.ok(controller);
assert.equal(controller.canLayerHair, true);
assert.equal(controller.indices.length,HIDE.length);
controller.sync(true);
assert.equal(calls.length,HIDE.length);
assert.ok(calls.every(([i,v])=>HIDE.includes(ids[i]) && v===0));
let captured;
controller.drawPass("rear",()=>{captured=Array.from(opacity);});
assert.deepEqual(captured,[initial[0],0,0,0,0]);
assert.deepEqual(Array.from(opacity),initial);
controller.drawPass("front",()=>{captured=Array.from(opacity);});
assert.deepEqual(captured,[0,initial[1],initial[2],0,0]);
assert.deepEqual(Array.from(opacity),initial);
assert.throws(()=>controller.drawPass("rear",()=>{throw Error("WebGL");}),/WebGL/);
assert.deepEqual(Array.from(opacity),initial);
controller.sync(false);
assert.equal(calls.length,HIDE.length*2);
assert.ok(calls.slice(-HIDE.length).every(([i,v])=>HIDE.includes(ids[i]) && v===1));
const broken={...core,getModel(){return {parts:{ids:["PartJAD_FACE"],count:1}}}};
assert.equal(window.JadeHeadIsolation.forModel(broken),null);
// Older SDKs may isolate the standing body, but must not enable the depth
// compositor unless the parent-part mapping is actually present.
const noHierarchy={...core,getModel(){return {parts:{ids,count:ids.length}}}};
assert.equal(window.JadeHeadIsolation.forModel(noHierarchy).canLayerHair,false);
const noAlphas={...core,getModel(){return {parts:{ids,count:ids.length,parentIndices:partParents},
  drawables:{count:5,parentPartIndices:drawableParents}};}};
assert.equal(window.JadeHeadIsolation.forModel(noAlphas).canLayerHair,false,
  "no renderer compositor without mutable drawable opacities");
console.log("Seated Jade: one Live2D model, rear hair -> body -> front hair");
