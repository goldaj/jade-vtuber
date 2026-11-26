/* Hybrid body lifecycle: real events, controlled image races, no GPU/network. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync("src/jade_runtime/mobile_web/seated-scene.js", "utf8");
const settle = () => new Promise(resolve => setImmediate(resolve));

function client({manual = false, available = true, composable = true, isolatable = true,
                 bodyHeight = 940, bodyWidth = 670, portraitWidth = 864,
                 full = false, avatarReady = true, roomName = "bedroom", composeThrows = false} = {}) {
  const handlers = {}, properties = {}, requests = [], calls = [];
  const room = {dataset:{room:roomName, avatarPresentation:full ? "full" : "seated"}, events:[],
    addEventListener(name, fn){(handlers[name] ||= []).push(fn);},
    dispatchEvent(event){this.events.push(event.type); for (const fn of handlers[event.type] || []) fn(event);}};
  const backdrop = {src:""};
  const body = {src:"", style:{
    setProperty(name, value){properties[name] = value;},
    removeProperty(name){delete properties[name];}},
    removeAttribute(name){if (name === "src") this.src = "";}};
  class ImageMock {
    constructor(){this.naturalWidth = 0; this.naturalHeight = 0; this.removed = false;}
    set src(url){
      this._src = url; this.kind = url.includes("seated-body") ? "body" : "portrait";
      requests.push(this);
      // Keep the original callbacks to simulate an event already queued when
      // a model switch cancels an image. Generation checks must still win.
      const loaded = this.onload, failed = this.onerror;
      this.finish = (success = available, width, height) => {
        this.naturalWidth = width ?? (this.kind === "body" ? bodyWidth : portraitWidth);
        this.naturalHeight = height ?? (this.kind === "body" ? bodyHeight : 1536);
        if (success) loaded(); else failed();
      };
      if (!manual) queueMicrotask(() => this.finish());
    }
    get src(){return this._src;}
    removeAttribute(name){if (name === "src") {this._src = ""; this.removed = true;}}
  }
  const avatar = {ready:avatarReady, usesSeatedBody:!full, canIsolateHead:isolatable, canComposeSeated:composable,
    prepareSeatedComposition(image){
      calls.push({type:"compose", image});
      if (composeThrows) throw new Error("renderer composition failed");
      return true;
    }, resize(){calls.push({type:"resize"});}};
  const window = {JadeAvatar:avatar};
  vm.runInNewContext(source, {
    console:{warn(){}}, Image:ImageMock, Promise, Event:class {constructor(type){this.type = type;}}, window,
    document:{querySelector(){return room;}, getElementById(id){
      return id === "portrait-bedroom" ? backdrop : id === "portrait-seated-body" ? body : null;}}
  });
  return {window, room, backdrop, body, properties, requests, calls, avatar,
    get scene(){return window.JadeSeatedScene;},
    image(kind, index = 0){return requests.filter(image => image.kind === kind)[index];},
    async switchTo(next, options = {}) {
      window.JadeSeatedScene.deactivate();
      avatar.ready = options.ready ?? true;
      avatar.usesSeatedBody = next === "classic";
      avatar.canIsolateHead = options.isolatable ?? true;
      avatar.canComposeSeated = options.composable ?? true;
      room.dataset.avatarPresentation = next === "classic" ? "seated" : "full";
      if (avatar.ready) room.dispatchEvent({type:"jade-avatar-ready"});
      await settle();
    }};
}

function assertCrop(a, bodyHeight) {
  const {top, height} = a.scene.layout;
  assert.ok(Math.abs(top + height - (.406699 + .562201)) < 1e-12, "neck extension preserves the bottom anchor");
  assert.ok(Math.abs(height / bodyHeight - .562201 / 940) < 1e-12, "neck extension preserves pixel scale");
  assert.ok(Math.abs(top + height * (bodyHeight - 940) / bodyHeight - .406699) < 1e-12);
  assert.ok(Math.abs(parseFloat(a.properties["--seated-body-top"]) / 100 - top) < 1e-12);
  assert.ok(Math.abs(parseFloat(a.properties["--seated-body-height"]) / 100 - height) < 1e-12);
}

(async () => {
  for (const bodyHeight of [940, 956]) {
    for (const composable of [false, true]) {
      const a = client({bodyHeight, composable}); await settle();
      assert.equal(a.requests.length, 2);
      assert.equal(a.scene.ready, true);
      assert.equal(a.room.dataset.seatedReady, "true");
      assert.equal(a.room.dataset.portraitReady, "true");
      assert.equal(a.room.dataset.seatedCompositor, String(composable));
      assert.equal(a.backdrop.src, "/assets/room-bedroom-portrait.avif");
      assert.equal(a.body.src, "/assets/jade-seated-body.avif");
      assert.equal(a.calls.filter(call => call.type === "compose").length, composable ? 1 : 0);
      assertCrop(a, bodyHeight);
      a.room.dispatchEvent({type:"jade-avatar-ready"}); await settle();
      assert.equal(a.requests.length, 2, "duplicate ready does not reload a working body");
    }
  }
  for (const options of [{bodyHeight:955}, {bodyWidth:671}, {portraitWidth:1200}, {available:false}]) {
    const a = client(options); await settle();
    assert.equal(a.scene.ready, false);
    assert.notEqual(a.room.dataset.portraitReady, "true", "first classic activation needs a complete valid pair");
    assert.equal(a.body.src, ""); assert.equal(a.backdrop.src, ""); assert.deepEqual(a.calls, []);
  }
  const isolated = client({isolatable:false}); await settle();
  assert.equal(isolated.requests.length, 0, "no seated asset work without an isolatable head");
  assert.equal(isolated.scene.ready, false);
  const thrown = client({composeThrows:true}); await settle();
  assert.equal(thrown.scene.ready, true);
  assert.equal(thrown.room.dataset.seatedCompositor, "false", "composition failure keeps the DOM seated body");
  assert.equal(thrown.body.src, "/assets/jade-seated-body.avif");

  const idle = client({avatarReady:false}); await settle();
  assert.equal(idle.requests.length, 0, "waiting for a renderer does not guess its body requirements");
  idle.avatar.ready = true; idle.room.dispatchEvent({type:"jade-avatar-ready"}); await settle();
  assert.equal(idle.scene.ready, true);

  for (const roomName of ["bedroom", "kitchen"]) {
    const a = client({roomName}); await settle();
    const backdrop = a.backdrop.src;
    a.scene.deactivate();
    assert.equal(a.scene.ready, false, "deactivation is synchronous");
    assert.equal(a.body.src, "", "DOM body image reference is released immediately");
    assert.deepEqual(a.properties, {}, "body-specific crop variables are cleared");
    assert.equal(a.room.dataset.seatedReady, "false");
    assert.equal(a.room.dataset.seatedCompositor, "false");
    assert.equal(a.room.dataset.portraitReady, "true", "approved portrait survives deactivation");
    assert.equal(a.backdrop.src, backdrop);
    await a.switchTo("next");
    assert.equal(a.requests.length, 2, "full model does not request another seated body");
    assert.equal(a.calls.filter(call => call.type === "compose").length, 1);
    assert.equal(a.room.dataset.room, roomName, "model changes never change the selected room");
    await a.switchTo("classic", {composable:false});
    assert.equal(a.scene.ready, true, "returning to classic prepares a fresh body");
    assert.equal(a.room.dataset.seatedCompositor, "false", "DOM fallback remains possible after returning");
    assert.equal(a.requests.filter(image => image.kind === "portrait").length, 1, "portrait cache is independent of the model");
    assert.equal(a.requests.filter(image => image.kind === "body").length, 2);
    await a.switchTo("next"); await a.switchTo("classic");
    assert.equal(a.room.dataset.seatedCompositor, "true", "layered composition can be recreated on a later return");
    assert.equal(a.calls.filter(call => call.type === "compose").length, 2);
    assert.equal(a.room.dataset.room, roomName);
  }

  const full = client({full:true, isolatable:false}); await settle();
  assert.equal(full.requests.length, 1); assert.equal(full.image("body"), undefined);
  assert.equal(full.room.dataset.portraitReady, "true");
  assert.equal(full.room.dataset.seatedReady, "false");
  assert.equal(full.body.src, ""); assert.equal(full.scene.ready, false);
  assert.equal(full.calls.filter(call => call.type === "compose").length, 0);

  const late = client({manual:true});
  const staleBody = late.image("body");
  await late.switchTo("next");
  assert.equal(staleBody.removed, true, "a pending body load is cancelled at selection");
  staleBody.finish(); late.image("portrait").finish(); await settle();
  assert.equal(late.room.dataset.portraitReady, "true");
  assert.equal(late.scene.ready, false); assert.equal(late.body.src, "");
  assert.equal(late.calls.filter(call => call.type === "compose").length, 0, "late old body never reaches the new renderer");
  await late.switchTo("classic");
  const freshBody = late.image("body", 1);
  freshBody.finish(true, 670, 956); await settle();
  assert.equal(late.scene.ready, true); assertCrop(late, 956);
  staleBody.finish(); await settle();
  assert.equal(late.calls.filter(call => call.type === "compose").length, 1);
  assert.equal(late.calls.find(call => call.type === "compose").image, freshBody,
    "a superseded response cannot replace the newly prepared body");

  const queued = client({manual:true});
  queued.image("portrait").finish(); queued.image("body").finish();
  // Both image promises are resolved, but their continuation has not run yet.
  await queued.switchTo("next");
  assert.equal(queued.scene.ready, false); assert.equal(queued.body.src, "");
  assert.equal(queued.calls.filter(call => call.type === "compose").length, 0,
    "generation check rejects an already resolved stale pair");

  const retained = client({manual:true, full:true});
  retained.image("portrait").finish(); await settle();
  const retainedBackdrop = retained.backdrop.src;
  await retained.switchTo("classic");
  retained.image("body").finish(true, 100, 100); await settle();
  assert.equal(retained.scene.ready, false);
  assert.equal(retained.room.dataset.portraitReady, "true", "a later invalid body cannot undo a previously valid room");
  assert.equal(retained.backdrop.src, retainedBackdrop); assert.equal(retained.body.src, "");

  const failedSwitch = client(); await settle();
  const stableBackdrop = failedSwitch.backdrop.src;
  await failedSwitch.switchTo("next", {ready:false});
  failedSwitch.room.dispatchEvent({type:"jade-avatar-state"}); await settle();
  assert.equal(failedSwitch.scene.ready, false, "a failed model with no ready event cannot restore the old body");
  assert.equal(failedSwitch.body.src, "");
  assert.equal(failedSwitch.backdrop.src, stableBackdrop);
  assert.equal(failedSwitch.room.dataset.portraitReady, "true");
  assert.equal(failedSwitch.requests.filter(image => image.kind === "body").length, 1);
  await failedSwitch.switchTo("classic");
  assert.equal(failedSwitch.scene.ready, true, "successful renderer rollback recreates the classic body");
  assert.equal(failedSwitch.requests.filter(image => image.kind === "body").length, 2);
  assert.equal(failedSwitch.room.dataset.seatedCompositor, "true");

  const failedBody = client({manual:true, full:true});
  failedBody.image("portrait").finish(); await settle();
  await failedBody.switchTo("classic"); failedBody.image("body").finish(false); await settle();
  assert.equal(failedBody.scene.ready, false); assert.equal(failedBody.body.src, "");
  assert.equal(failedBody.room.dataset.portraitReady, "true");
  await failedBody.switchTo("next"); await failedBody.switchTo("classic");
  failedBody.image("body", 1).finish(); await settle();
  assert.equal(failedBody.scene.ready, true, "body image failure does not poison a later classic return");
  console.log("Seated scene: atomic startup, independent portrait, classic/full/classic, DOM/compositor and stale-image isolation PASS");
})().catch(error => {console.error(error); process.exitCode = 1;});
