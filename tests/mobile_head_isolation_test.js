"use strict";
const assert=require("node:assert/strict");
const vm=require("node:vm");
const fs=require("node:fs");
const source=fs.readFileSync("src/jade_runtime/mobile_web/head-isolation.js","utf8");
const HIDE=[
 "PartJAD_BODY","PartJAD_BODY_SKIN","PartJAD_ARM_L","PartJAD_ARM_R",
 "PartJAD_DRESS","PartJAD_DRESS_SLEEVE_L","PartJAD_DRESS_SLEEVE_R","PartJAD_DRESS_SKIRT"
];
const window={};vm.runInNewContext(source,{window});
const calls=[];
const ids=["PartJAD_ROOT",...HIDE,"PartJAD_FACE","PartJAD_HAIR_FRONT","PartJAD_HAIR_AHOGE"];
const core={
 getModel(){return {parts:{ids,count:ids.length}};},
 getPartCount(){return ids.length;},
 setPartOpacityByIndex(index,opacity){calls.push([index,opacity]);},
 getPartOpacityByIndex(){return 1;}
};
const controller=window.JadeHeadIsolation.forModel(core);
assert.ok(controller,"known r20 parts must be recognized");
assert.equal(controller.indices.length,HIDE.length);
controller.sync(true);
assert.equal(calls.length,HIDE.length);
assert.ok(calls.every(([i,v])=>HIDE.includes(ids[i])&&v===0));
controller.sync(false);
assert.equal(calls.length,HIDE.length*2);
assert.ok(calls.slice(-HIDE.length).every(([i,v])=>HIDE.includes(ids[i])&&v===1));
const broken={...core,getModel(){return {parts:{ids:["PartJAD_FACE"],count:1}}}};
assert.equal(window.JadeHeadIsolation.forModel(broken),null);
console.log("Seated Jade: body hidden, head and moving hair preserved");
