/* Execute with Node: exercises fragmented UTF-8/NDJSON, PCM and cancellation. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const elements = new Map();
function element(id) {
  if (!elements.has(id)) {
    const classes = new Set();
    elements.set(id, {
    id, value:"", textContent:"", disabled:false, open:false, children:[], handlers:{},
    classList:{add(name){classes.add(name);}, remove(name){classes.delete(name);},
      contains(name){return classes.has(name);}},
    addEventListener(name, handler) {this.handlers[name] = handler;},
    append(...children) {this.children.push(...children);},
    appendChild(child) {this.children.push(child);},
    replaceChildren() {this.children = [];},
    setAttribute(){}, focus(){}, querySelector(){return element("fake-submit");}
    });
  }
  return elements.get(id);
}
const documentHandlers = {}, windowHandlers = {};
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
const played = [], stopped = [], performanceEvents = [];
let clockMs = 1000;
Object.defineProperty(global, "performance", {value:{now:() => clockMs}, configurable:true});
let microphoneProcessor;
class AudioContext {
  constructor() { this.destination = {}; this.sampleRate = 48000; }
  get currentTime() {return clockMs / 1000;}
  resume() {return Promise.resolve();}
  close() {return Promise.resolve();}
  createMediaStreamSource() {return {connect(){}, disconnect(){}};}
  createScriptProcessor() {return microphoneProcessor = {connect(){}, disconnect(){}};}
  createGain() {return {gain:{}, connect(){}, disconnect(){}};}
  createBuffer(channels, length, rate) {
    const samples = new Float32Array(length);
    return {duration:length/rate, getChannelData:() => samples};
  }
  createAnalyser() {return {connect(){}, disconnect(){}, getByteTimeDomainData(a){a.fill(128);}};}
  decodeAudioData() {return Promise.resolve(this.createBuffer(1, 2, 24000));}
  createBufferSource() {return {connect(){}, disconnect(){}, stop(){stopped.push(this);},
    start(when) {this.when = when; played.push(this); performanceEvents.push(["audio"]);}};}
}
const avatar = {
  setMouth(){}, setSpeaking(){},
  setIntent(intent, {deferMotion} = {}) {performanceEvents.push(["pose", intent, deferMotion]); return true;},
  startReplyMotion(delayMs) {performanceEvents.push(["gesture", delayMs]);},
  finishReply() {performanceEvents.push(["finish"]);},
  resetIntent() {performanceEvents.push(["reset"]);},
};
global.window = {crypto:global.crypto, AudioContext, JadeAvatar:avatar,
  location:{hash:""}, addEventListener(name, handler) {(windowHandlers[name] ||= []).push(handler);},
  setTimeout, clearTimeout};
const mic = element("mic");
function press(pointerId = 1) {
  return mic.handlers.pointerdown({button:0, isPrimary:true, pointerId, preventDefault(){}});
}
function mouseEnds(type = "pointerup", pointerId = 1) {
  for (const handler of windowHandlers[type]) handler({pointerId});
}
function sample(value = 0) {
  microphoneProcessor.onaudioprocess({inputBuffer:{getChannelData:() => new Float32Array(4096).fill(value)}});
}
const tick = () => new Promise(resolve => setImmediate(resolve));
const pcmEvent = {type:"pcm", sample_rate:24000, pcm_b64:Buffer.from([0,128,255,127]).toString("base64")};
let fetchCount = 0, lastSignal, finishLegacyReply, wavRequest, releaseTail;
global.fetch = async (_path, options) => {
  // The login handshake is independent of paid chat and streaming turns.
  if (_path === "/api/auth") {
    assert.equal(options.method, "POST");
    assert.equal(options.headers.Authorization, "Bearer " + "x".repeat(40));
    return {status:200, ok:true, json:async () => ({status:"ok"})};
  }
  lastSignal = options.signal;
  fetchCount++;
  if (_path === "/api/voice") {
    wavRequest = options;
    return {status:200, ok:true, json:async () => ({reply:"Voix de secours", intent:"tender", audio_wav_b64:"AA=="})};
  }
  if (fetchCount === 3) {
    assert.equal(options.headers["X-Jade-Stream"], undefined);
    return {status:200, ok:true, json:async () => ({reply:"Ancien navigateur", intent:"curious", audio_wav_b64:"AA=="})};
  }
  if (fetchCount === 4) {
    return {status:200, ok:true, json:() => new Promise(resolve => {finishLegacyReply = resolve;})};
  }
  const serialize = events => Buffer.from(events.map(event => JSON.stringify(event) + "\n").join(""));
  const initial = serialize([{type:"reply", reply:"Salut, à toi !", intent:"serious"}, pcmEvent]);
  const bytes = Buffer.concat([initial, serialize([pcmEvent, {type:"done"}])]);
  let offset = 0;
  return {status:200, ok:true, body:{getReader(){return {async read() {
    if (fetchCount === 2) return new Promise((resolve, reject) => {
      options.signal.addEventListener("abort", () => reject(new Error("aborted")), {once:true});
    });
    if (offset >= bytes.length) return {done:true};
    if (offset === initial.length) await new Promise(resolve => {releaseTail = resolve;});
    const boundary = offset < initial.length ? initial.length : bytes.length;
    const part = bytes.subarray(offset, Math.min(offset + 3, boundary)); offset += part.length;
    return {done:false, value:part};
  }};}}};
};
vm.runInThisContext(fs.readFileSync(path.join(__dirname, "../src/jade_runtime/mobile_web/app.js"), "utf8"));

(async () => {
  window.JadeMobileApp.login("x".repeat(40));
  element("message").value = "Bonjour";
  const streaming = element("composer").handlers.submit({preventDefault(){}});
  await tick();
  assert.equal(played.length, 1);
  assert.deepEqual(Array.from(played[0].buffer.getChannelData(0)), [-1, 32767 / 32768]);
  assert.equal(element("messages").children[1].children[0].textContent, "Salut, à toi !");
  const firstPose = performanceEvents.findIndex(([event]) => event === "pose");
  assert.deepEqual(performanceEvents[firstPose], ["pose", "serious", true]);
  assert(firstPose < performanceEvents.findIndex(([event]) => event === "audio"));
  assert(played[0].when >= 1.199, "the first PCM chunk gives the facial pose time to show");
  played[0].onended();
  clockMs += 400;
  assert.equal(performanceEvents.some(([event]) => event === "finish"), false,
    "an empty PCM queue between packets must not end the expression");
  releaseTail();
  await streaming;
  assert.equal(played.length, 2);
  assert.equal(played[1].when, clockMs / 1000,"a late packet resumes without an added pause");
  assert.equal(performanceEvents.filter(([event]) => event === "gesture").length, 1,
    "the same gesture follows the whole reply, even after a network gap");
  assert.equal(performanceEvents.some(([event]) => event === "finish"), false,
    "server done must wait for the last scheduled sound");
  played.at(-1).onended();
  assert.deepEqual(performanceEvents.at(-1), ["finish"]);
  assert.equal(performanceEvents.filter(([event]) => event === "finish").length, 1);
  let resume = window.JadeConversation.stopForModelChange();
  assert.equal(stopped.length, 0);
  assert.equal(element("mic").disabled, true);
  assert.equal(element("send").disabled, true);
  resume();
  assert.equal(element("mic").disabled, false);
  assert.equal(element("send").disabled, false);
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
  const interruptedWav = played.at(-1), staleWavEnd = interruptedWav.onended;
  assert.equal(typeof staleWavEnd, "function");
  const finishesBeforeSwitch = performanceEvents.filter(([event]) => event === "finish").length;
  resume = window.JadeConversation.stopForModelChange();
  assert.equal(stopped.at(-1), interruptedWav);
  assert.deepEqual(performanceEvents.at(-1), ["reset"]);
  resume();
  staleWavEnd();
  assert.equal(performanceEvents.filter(([event]) => event === "finish").length, finishesBeforeSwitch,
    "a queued callback from the previous model must not close a later pose");

  element("message").value = "Réponse tardive";
  const late = element("composer").handlers.submit({preventDefault(){}});
  await new Promise(resolve => setImmediate(resolve));
  resume = window.JadeConversation.stopForModelChange();
  assert.equal(lastSignal.aborted, true);
  finishLegacyReply({reply:"À ignorer"});
  await late;
  assert.equal(element("send").disabled, true);
  assert.equal(element("messages").children.at(-1).children[0].textContent, "Réponse tardive");
  resume();

  let grantMicrophone, stops = 0;
  const mediaStream = {getTracks:() => [{stop() {stops++;}}]};
  navigator.mediaDevices = {getUserMedia:() => new Promise(resolve => {grantMicrophone = resolve;})};
  press();
  resume = window.JadeConversation.stopForModelChange();
  grantMicrophone(mediaStream);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(stops, 1);
  assert.equal(element("mic").disabled, true);
  assert.equal(element("mic").classList.contains("recording"), false);
  resume();

  press();
  mouseEnds();
  grantMicrophone(mediaStream);
  await tick();
  assert.equal(stops, 2, "a late permission grant after release must close its tracks");
  assert.match(element("status").textContent, /relâché avant le début/);
  assert.equal(fetchCount, 4, "releasing during permission must never start a turn");

  navigator.mediaDevices.getUserMedia = async () => mediaStream;
  let cancelled = 0, emitDuplex;
  window.JadeDuplex = {
    supported: () => true,
    create({onEvent}) {emitDuplex = onEvent; return {cancel() {cancelled++;}};}
  };
  await press();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(element("mic").classList.contains("recording"), true);
  resume = window.JadeConversation.stopForModelChange();
  assert.equal(stops, 3);
  assert.equal(cancelled, 1);
  assert.equal(element("mic").classList.contains("recording"), false);
  await emitDuplex({type:"reply", reply:"À ignorer également"});
  assert.equal(element("messages").children.at(-1).children[0].textContent, "Réponse tardive");
  resume();
  assert.equal(element("mic").disabled, false);
  assert.equal(fetchCount, 4);

  let finished = 0, frames = 0, finishVoice, disconnectVoice;
  window.JadeDuplex = {
    supported: () => true,
    create({onEvent, onDisconnect}) {
      emitDuplex = onEvent;
      disconnectVoice = onDisconnect;
      return {ready:true,
        push(part) {frames += part.length;},
        finish() {finished++; return new Promise(resolve => {finishVoice = resolve;});},
        cancel() {cancelled++;}
      };
    }
  };
  await press();
  const realNow = Date.now;
  try {
    let time = realNow();
    Date.now = () => time;
    sample(.3);
    time += 1600;
    sample(0);
    time += 1600;
    sample(.2);
  } finally { Date.now = realNow; }
  assert.equal(frames, 12288, "all chunks, including silence, stream during the push");
  assert.equal(finished, 0, "silence must not finish the utterance while held");
  assert.equal(mic.classList.contains("recording"), true);
  assert.equal(element("mic-feedback").hidden, false);
  assert.match(element("mic-feedback").textContent, /Relâche pour envoyer/);
  mouseEnds("pointerup", 2);
  assert.equal(finished, 0, "another pointer must not stop the capture");
  mouseEnds();
  mouseEnds();
  mic.handlers.click?.({preventDefault(){}});
  assert.equal(finished, 1, "one release ends the utterance once even if it produces a click");
  assert.equal(stops, 4, "release closes the microphone immediately");
  await emitDuplex({type:"reply", reply:"Je t’écoute", intent:"reassuring"});
  await emitDuplex(pcmEvent);
  await emitDuplex({type:"done"});
  assert.notDeepEqual(performanceEvents.at(-1), ["finish"], "duplex done also waits for playback");
  played.at(-1).onended();
  assert.deepEqual(performanceEvents.at(-1), ["finish"]);
  finishVoice();
  await tick();
  assert.equal(element("mic-feedback").hidden, true, "ready clears the visible voice feedback");

  await press();
  sample(.15);
  mouseEnds("pointercancel");
  assert.equal(cancelled, 2);
  assert.equal(finished, 1, "an interrupted hold must discard capture");
  assert.equal(stops, 5);

  await press();
  sample(.15);
  disconnectVoice(new Error("Connexion vocale indisponible."));
  assert.equal(stops, 6, "loss of the ready socket stops the live microphone");
  assert.match(element("status").textContent, /Connexion vocale indisponible/);
  assert.equal(fetchCount, 4, "no WAV retry after the socket accepted this turn");

  const key = (name, repeat = false) => ({key:name, repeat, preventDefault(){}});
  await mic.handlers.keydown(key(" "));
  await mic.handlers.keydown(key(" ", true));
  sample(.2); sample(.2); sample(.2);
  mic.handlers.keyup(key(" "));
  assert.equal(finished, 2, "Space uses the same press and release lifecycle");
  finishVoice();
  await tick();

  await press();
  const beforeLimit = frames;
  const beforeLimitClosed = stops;
  for (let i = 0; i < Math.ceil(960000 / 4096); i++) sample(.1);
  assert.equal(frames - beforeLimit, 960000, "bounded capture: exactly 20 seconds of PCM");
  assert.equal(stops, beforeLimitClosed + 1);
  assert.equal(finished, 2, "the limit closes the microphone and waits for release");
  assert.match(element("mic-feedback").textContent, /Limite de 20 s/);
  mouseEnds();
  assert.equal(finished, 3);
  assert.equal(stops, beforeLimitClosed + 1, "release after the limit does not stop the tracks twice");
  finishVoice();
  await tick();

  window.JadeDuplex.create = () => ({
    ready:false, push(){},
    async finish(){throw new Error("Le socket n’a pas été authentifié.");},
    cancel(){}
  });
  await press();
  sample(.2); sample(.2); sample(.2);
  assert.equal(fetchCount, 4, "the safe fallback waits for release");
  mouseEnds();
  await tick();
  assert.equal(fetchCount, 5);
  assert.equal(wavRequest.body.type, "audio/wav");
  assert.equal(element("messages").children.at(-1).children[0].textContent, "Voix de secours");
  assert.notDeepEqual(performanceEvents.at(-1), ["finish"], "the fallback waits for its WAV source");
  played.at(-1).onended();
  assert.deepEqual(performanceEvents.at(-1), ["finish"]);
  process.stdout.write("Mobile stream client: OK\n");
})().catch(error => {console.error(error); process.exitCode = 1;});
