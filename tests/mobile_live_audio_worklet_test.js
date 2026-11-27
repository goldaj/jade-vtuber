/* Deterministic PCM algorithm checks, not an acoustic/device qualification. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

let Capture;
class Processor {
  constructor() { this.messages = []; this.port = {postMessage:value => this.messages.push(value)}; }
}
vm.runInNewContext(fs.readFileSync(path.join(__dirname,
  "../src/jade_runtime/mobile_web/live-audio-worklet.js"), "utf8"), {
  AudioWorkletProcessor:Processor, sampleRate:1000,
  registerProcessor(name, implementation) { assert.equal(name, "jade-live-capture"); Capture = implementation; }
});
function feed(capture, amplitude, frames = 1, output = []) {
  for (let i = 0; i < frames; i++) {
    const samples = new Float32Array(10).fill(amplitude);
    const played = new Float32Array(10);
    assert.equal(capture.process([[samples]], [[played]]), true);
    output.push(...played);
  }
  return output;
}
function command(capture, type) { capture.port.onmessage({data:{type}}); }

{
  const capture = new Capture();
  const beforeConnection = feed(capture, .001, 100);
  assert.equal(capture.length, 500, "quiet local capture retains exactly the bounded pre-roll");
  for (let i = 0; i < 6; i++) feed(capture, .1 + i / 100, 1, beforeConnection);
  assert.equal(capture.messages.filter(event => event.type === "speech").length, 1);
  assert.equal(capture.length, 560, "pre-roll precedes the very first threshold, not the confirmed VAD event");
  feed(capture, .2, 20, beforeConnection);
  assert(beforeConnection.every(sample => sample === 0), "nothing is transmitted before the WebRTC connection is ready");
  command(capture, "connected");
  const actual = feed(capture, .3, 76);
  const expected = [...new Float32Array(500).fill(.001)];
  for (let i = 0; i < 6; i++) expected.push(...new Float32Array(10).fill(.1 + i / 100));
  expected.push(...new Float32Array(200).fill(.2));
  assert.deepEqual(actual, expected, "all cold pre-roll and phrase samples are injected once, in their original order");
  assert(capture.messages.some(event => event.type === "sent_speech"));
  assert(capture.messages.every(event => !event.pcm && !event.samples), "PCM never goes through control messages");
  command(capture, "local");
  assert.equal(capture.length, 0);
  assert(capture.samples.every(sample => sample === 0), "idle generation transition erases old audio");
  feed(capture, .15, 6);
  assert.equal(capture.messages.filter(event => event.type === "speech").length, 2,
    "new local speech wakes a new generation after an idle close");
}
{
  const capture = new Capture();
  feed(capture, 0, 50);
  feed(capture, .2, 750);
  assert.equal(capture.length, 8000, "8 s includes the initial 500 ms pre-roll");
  assert.equal(capture.messages.some(event => event.type === "overflow"), false);
  feed(capture, .2);
  assert.equal(capture.mode, "failed");
  assert.equal(capture.length, 0);
  assert.equal(capture.messages.filter(event => event.type === "overflow").length, 1);
  assert(capture.samples.every(sample => sample === 0));
  command(capture, "connected");
  assert(feed(capture, .3).every(value => value === 0), "an overflow cannot silently resume with truncated words");
}
{
  const capture = new Capture();
  feed(capture, .2, 6);
  feed(capture, 0, 150);
  command(capture, "connected");
  feed(capture, 0, 156);
  const before = capture.length;
  feed(capture, 0, 1);
  assert(capture.length < before, "catch-up is allowed only after the protected first phrase, inside silence");
  command(capture, "stop");
  const output = new Float32Array(10).fill(1);
  assert.equal(capture.process([[new Float32Array(10)]], [[output]]), false);
  assert(output.every(value => value === 0));
  assert.equal(capture.length, 0);
}
console.log("Mobile Live AudioWorklet: OK (synthetic PCM only)");
