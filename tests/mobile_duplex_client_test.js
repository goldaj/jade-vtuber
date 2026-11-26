"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../src/jade_runtime/mobile_web/duplex-client.js"), "utf8");

function client() {
  let socket, timeout;
  const sent = [], events = [], interruptions = [];
  const window = {};
  class WebSocket {
    static OPEN = 1;
    static CLOSING = 2;
    readyState = 0;
    bufferedAmount = 0;
    constructor() { socket = this; }
    send(frame) { sent.push(typeof frame === "string" ? JSON.parse(frame) : frame.byteLength); }
    close() { this.readyState = 3; }
  }
  vm.runInNewContext(source, {
    window, WebSocket, location:{protocol:"https:", host:"jade.local"},
    setTimeout(callback, delay) { assert.equal(delay, 2500); timeout = callback; return 1; },
    clearTimeout() { timeout = null; },
  });
  const voice = window.JadeDuplex.create({
    token:"fixture", session:"mobile-test", speak:false,
    onEvent:event => events.push(event.type), onDisconnect:error => interruptions.push(error.message),
  });
  return {
    voice, socket, sent, events, interruptions,
    open() { socket.readyState = WebSocket.OPEN; socket.onopen(); },
    async receive(type) {
      socket.onmessage({data:JSON.stringify({type})});
      await new Promise(resolve => setImmediate(resolve));
    },
    expire() { timeout(); },
    get pendingTimeout() { return Boolean(timeout); },
  };
}

async function main() {
  const samples = new Float32Array(4000).fill(.15);
  const streaming = client();
  streaming.open();
  streaming.voice.push(samples, 16000);
  assert.deepEqual(streaming.sent.map(frame => frame.type), ["auth"]);
  await streaming.receive("ready");
  assert.equal(streaming.pendingTimeout, false);
  streaming.voice.push(samples, 16000);
  assert.deepEqual(streaming.sent.slice(1), [{type:"start", speak:false}, 8000, 8000]);
  const first = streaming.voice.finish(), second = streaming.voice.finish();
  assert.equal(streaming.sent.filter(frame => frame.type === "end").length, 1);
  await streaming.receive("done");
  await Promise.all([first, second]);
  assert.deepEqual(streaming.events, ["done"]);

  const slow = client();
  slow.open();
  slow.voice.push(samples, 16000);
  slow.expire();
  await slow.receive("ready");
  await assert.rejects(slow.voice.finish(), /trop lente/);
  assert.equal(slow.voice.ready, false);
  assert.equal(slow.sent.length, 1, "the late handshake cannot send buffered speech");
  assert.equal(slow.interruptions.length, 0, "before ready, the WAV fallback is still possible");

  const overflow = client();
  for (let i = 0; i < 11; i++) overflow.voice.push(samples, 16000);
  await assert.rejects(overflow.voice.finish(), /trop lente/);
  assert.equal(overflow.voice.ready, false);
  assert.equal(overflow.socket.readyState, 3);

  const dropped = client();
  dropped.open();
  await dropped.receive("ready");
  dropped.socket.onerror();
  dropped.socket.onclose();
  assert.equal(dropped.interruptions.length, 1, "notify the active capture only once after ready");
  assert.equal(dropped.voice.ready, true, "a failed authenticated turn is never replayed");
  await assert.rejects(dropped.voice.finish(), /indisponible/);

  const cancelled = client();
  cancelled.open();
  await cancelled.receive("ready");
  cancelled.voice.cancel();
  await assert.rejects(cancelled.voice.finish(), /interrompue/);
  await cancelled.receive("reply");
  assert.deepEqual(cancelled.events, [], "no reply after cancellation");
  assert.equal(cancelled.interruptions.length, 0, "a local cancellation is not a connection failure");
  console.log("Mobile PCM transport: streaming before release, one end, bounded setup and interruption PASS");
}

main().catch(error => { console.error(error); process.exitCode = 1; });
