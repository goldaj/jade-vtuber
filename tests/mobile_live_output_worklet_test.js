/* Deterministic PCM checks for the optional mobile Live playback effect. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname,
  "../src/jade_runtime/mobile_web/live-output-worklet.js"), "utf8");

function createOutput(sampleRate) {
  let Output;
  class Processor {
    constructor() {
      this.messages = [];
      this.port = {postMessage: message => this.messages.push(message)};
    }
  }
  vm.runInNewContext(source, {
    AudioWorkletProcessor: Processor,
    sampleRate,
    registerProcessor(name, implementation) {
      assert.equal(name, "jade-live-output");
      Output = implementation;
    }
  });
  return new Output({processorOptions: {speed: 1.10}});
}

function play(processor, input, length = input?.length ?? 10, active = true) {
  const output = new Float32Array(length).fill(1);
  assert.equal(processor.process([input ? [input] : []], [[output]]), active);
  return output;
}

function feed(processor, amplitude, blocks, result = []) {
  const input = new Float32Array(10).fill(amplitude);
  for (let block = 0; block < blocks; block++) result.push(...play(processor, input));
  return result;
}

function command(processor, type) {
  processor.port.onmessage({data: {type}});
}

function states(processor) {
  return processor.messages.filter(event => event.type === "state").map(event => event.state);
}

{
  const processor = createOutput(1000);
  assert(feed(processor, .0005, 100).every(sample => sample === 0));
  assert.equal(processor.size, 20, "silence only retains the 20 ms preroll");
  const result = feed(processor, .10, 4);
  feed(processor, -.20, 2, result);
  feed(processor, 0, 15, result);
  assert.deepEqual(states(processor), ["buffering"]);
  assert(result.every(sample => sample === 0), "wait for the initial reserve");
  feed(processor, 0, 38, result);
  assert.deepEqual(states(processor), ["buffering", "playing", "idle"]);
  const firstSound = result.findIndex(sample => sample !== 0);
  assert(firstSound >= 210 && firstSound <= 240);
  assert(Math.abs(result[firstSound] - .0005) < 1e-6, "preserve quiet preroll before the attack");
  assert(result.some(sample => sample > .09), "play the start of the short utterance");
  assert(result.some(sample => sample < -.19), "play the end of the short utterance");
  assert.equal(processor.size, 20, "return to bounded preroll following silence");

  const nextTurn = feed(processor, .30, 5);
  feed(processor, 0, 55, nextTurn);
  assert(nextTurn.some(sample => sample > .29), "the next utterance is audible");
  assert(nextTurn.every(sample => sample >= 0), "previous audio stays out of the next utterance");
  assert.deepEqual(states(processor), ["buffering", "playing", "idle", "buffering", "playing", "idle"]);
  assert(processor.messages.every(event => !event.pcm && !event.samples));
}

{
  const sampleRate = 48000;
  const processor = createOutput(sampleRate);
  const input = new Float32Array(128);
  const recording = new Float32Array(sampleRate * 8);
  const frequency = 220;
  for (let offset = 0; offset < recording.length; offset += input.length) {
    for (let frame = 0; frame < input.length; frame++) {
      input[frame] = .2 * Math.sin(2 * Math.PI * frequency * (offset + frame) / sampleRate);
    }
    recording.set(play(processor, input), offset);
  }

  const onset = recording.findIndex(sample => Math.abs(sample) > .01);
  assert(onset > .23 * sampleRate && onset < .25 * sampleRate);
  function measurePitch(start, duration) {
    let periodCount = 0;
    const first = onset + Math.floor(start * sampleRate);
    for (let index = first; index < first + Math.floor(duration * sampleRate); index++) {
      if (recording[index - 1] <= 0 && recording[index] > 0) periodCount++;
    }
    return periodCount / duration;
  }
  assert(Math.abs(measurePitch(.1, .5) - 242) <= 2, "the first audio plays at 1.10x speed and pitch");
  assert(Math.abs(measurePitch(6.5, 1) - 220) <= 2, "sustained speech eases smoothly toward the incoming rate");
  let silentSamples = 0;
  for (let index = onset; index < recording.length; index++) {
    silentSamples = Math.abs(recording[index]) < 1e-5 ? silentSamples + 1 : 0;
    assert(silentSamples < 6, "sustained speech plays without buffer underruns");
  }
  assert(processor.size >= 1900 && processor.size < 2400, "playback retains about 40 ms of audio");
  assert.deepEqual(states(processor), ["buffering", "playing"]);
}

{
  const processor = createOutput(1000);
  feed(processor, .16, 4);
  feed(processor, -.24, 2);
  command(processor, "drain");
  const tail = [];
  for (let block = 0; block < 8; block++) tail.push(...play(processor, null));
  assert(tail.some(sample => sample > .15));
  assert(tail.some(sample => sample < -.23));
  assert.deepEqual(states(processor), ["buffering", "playing", "drained"]);
  assert.equal(processor.size, 0, "terminal draining releases buffered PCM");
  assert(feed(processor, .50, 30).every(sample => sample === 0), "completed drain ignores later input");
  command(processor, "drain");
  assert.deepEqual(states(processor), ["buffering", "playing", "drained"]);

  command(processor, "reset");
  const nextTurn = feed(processor, .30, 25);
  assert(nextTurn.some(sample => sample > .29), "reset arms a new utterance");
  command(processor, "stop");
  assert(play(processor, null, 10, false).every(sample => sample === 0));
  assert.equal(processor.size, 0);
  assert(processor.samples.every(sample => sample === 0), "stop erases buffered audio immediately");
}

{
  const processor = createOutput(1000);
  const output = play(processor, new Float32Array(751).fill(.3), 10, false);
  assert(output.every(sample => sample === 0));
  assert.equal(processor.size, 0);
  assert.equal(processor.messages.filter(event => event.type === "overflow").length, 1);
}

console.log("Mobile Live Output AudioWorklet: OK (synthetic PCM only)");
