/* Execute with Node: exercises fragmented UTF-8/NDJSON, PCM and cancellation. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {
    id, value:"", textContent:"", disabled:false, open:false, children:[], handlers:{},
    classList:{add(){}, remove(){}},
    addEventListener(name, handler) {this.handlers[name] = handler;},
    append(...children) {this.children.push(...children);},
    appendChild(child) {this.children.push(child);},
    replaceChildren() {this.children = [];},
    setAttribute(){}, focus(){}, querySelector(){return element("fake-submit");}
  });
  return elements.get(id);
}
const documentHandlers = {};
global.document = {
  hidden:false, getElementById:element,
  querySelector: selector => selector === ".shell" ? Object.assign(element("test-shell"), {dataset:{view:"chat"}}) : null,
  querySelectorAll: () => [],
  createElement:tag => ({tag, children:[],
    append(...children) {this.children.push(...children);}}),
  addEventListener(name, handler) {documentHandlers[name] = handler;},
  documentElement:{}
};
Object.defineProperty(global, "navigator", {value:{}, configurable:true});
Object.defineProperty(global, "crypto", {value:{randomUUID: () => "01234567-89ab-cdef-0123-456789abcdef"}, configurable:true});
global.requestAnimationFrame = () => 1;
global.cancelAnimationFrame = () => {};
global.setInterval = () => 1;
const played = [];
class AudioContext {
  constructor() { this.currentTime = 1; this.destination = {}; }
  resume() {return Promise.resolve();}
  createBuffer(channels, length, rate) {
    const samples = new Float32Array(length);
    return {duration:length/rate, getChannelData:() => samples};
  }
  createAnalyser() {return {connect(){}, disconnect(){}, getByteTimeDomainData(a){a.fill(128);}};}
  createBufferSource() {return {connect(){}, disconnect(){}, stop(){},
    start() {played.push(Array.from(this.buffer.getChannelData(0)));}};}
}
const avatar = {setMouth(){}, setIntent(){}, setSpeaking(){}, resetIntent(){}};
global.window = {crypto:global.crypto, AudioContext, JadeAvatar:avatar,
  location:{hash:""}, addEventListener(){}, setTimeout, clearTimeout};
let fetchCount = 0, lastSignal;
global.fetch = async (_path, options) => {
  // The login handshake is independent of paid chat and streaming turns.
  if (_path === "/api/auth") {
    assert.equal(options.method, "POST");
    assert.equal(options.headers.Authorization, "Bearer " + "x".repeat(40));
    return {status:200, ok:true, json:async () => ({status:"ok"})};
  }
  lastSignal = options.signal;
  fetchCount++;
  if (fetchCount === 3) {
    assert.equal(options.headers["X-Jade-Stream"], undefined);
    return {status:200, ok:true, json:async () => ({reply:"Ancien navigateur", intent:"neutral"})};
  }
  const events = [
    {type:"reply", reply:"Salut, à toi !", intent:"neutral"},
    {type:"pcm", sample_rate:24000, pcm_b64:Buffer.from([0,128,255,127]).toString("base64")},
    {type:"done"}
  ];
  const bytes = Buffer.from(events.map(event => JSON.stringify(event) + "\n").join(""));
  let offset = 0;
  return {status:200, ok:true, body:{getReader(){return {read() {
    if (fetchCount === 2) return new Promise((resolve, reject) => {
      options.signal.addEventListener("abort", () => reject(new Error("aborted")), {once:true});
    });
    if (offset >= bytes.length) return Promise.resolve({done:true});
    const part = bytes.subarray(offset, offset + 3); offset += 3;
    return Promise.resolve({done:false, value:part});
  }};}}};
};
vm.runInThisContext(fs.readFileSync(path.join(__dirname, "../src/jade_runtime/mobile_web/app.js"), "utf8"));

(async () => {
  window.JadeMobileApp.login("x".repeat(40));
  element("message").value = "Bonjour";
  await element("composer").handlers.submit({preventDefault(){}});
  assert.equal(played.length, 1);
  assert.equal(played[0][0], -1);
  assert.equal(played[0][1], 32767 / 32768);
  assert.equal(element("messages").children[1].children[0].textContent, "Salut, à toi !");
  element("message").value = "Encore";
  const pending = element("composer").handlers.submit({preventDefault(){}});
  await new Promise(resolve => setImmediate(resolve));
  document.hidden = true;
  documentHandlers.visibilitychange();
  await pending;
  assert.equal(lastSignal.aborted, true);
  document.hidden = false;
  global.ReadableStream = undefined;
  element("message").value = "Compatibilité";
  await element("composer").handlers.submit({preventDefault(){}});
  assert.equal(fetchCount, 3);
  assert.equal(element("messages").children.at(-1).children[0].textContent, "Ancien navigateur");
  process.stdout.write("Mobile stream client: OK\n");
})().catch(error => {console.error(error); process.exitCode = 1;});
