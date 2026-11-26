/* Audio stays in this bounded, in-memory WebRTC source. No PCM leaves the
 * worklet through messages, storage, the control socket or another STT path. */
"use strict";
class JadeLiveCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.capacity = Math.ceil(sampleRate * 8);
    this.preroll = Math.ceil(sampleRate * .5);
    this.samples = new Float32Array(this.capacity);
    this.voiced = new Uint8Array(this.capacity);
    this.head = 0;
    this.length = 0;
    this.mode = "local";
    this.noise = .002;
    this.candidate = 0;
    this.hangover = 0;
    this.speech = false;
    this.sentSpeech = false;
    this.protected = 0;
    this.port.onmessage = ({data}) => {
      if (data?.type === "connected" && this.mode === "opening") {
        this.mode = "streaming";
        this.protected = this.length;
      }
      else if (data?.type === "local") this.reset("local");
      else if (data?.type === "stop") this.reset("stopped");
    };
  }

  reset(mode) {
    this.samples.fill(0);
    this.voiced.fill(0);
    this.head = this.length = this.candidate = this.hangover = this.protected = 0;
    this.speech = this.sentSpeech = false;
    this.mode = mode;
    this.port.postMessage({type:"speech_activity", active:false});
  }

  drop(count) {
    // Wipe consumed/discarded samples, including local pre-roll on quiet input.
    for (let i = 0; i < count; i++) {
      const index = (this.head + i) % this.capacity;
      this.samples[index] = 0;
      this.voiced[index] = 0;
    }
    this.head = (this.head + count) % this.capacity;
    this.length -= count;
  }

  process(inputs, outputs) {
    const output = outputs[0]?.[0];
    if (output) output.fill(0);
    if (this.mode === "stopped") return false;
    if (this.mode === "failed") return true;
    const input = inputs[0]?.[0];
    if (!input?.length) return true;
    let power = 0;
    for (let i = 0; i < input.length; i++) power += input[i] * input[i];
    const rms = Math.sqrt(power / input.length);
    const voice = rms >= Math.max(.012, this.noise * 3.5);
    if (!voice) this.noise = Math.min(.025, this.noise * .995 + rms * .005);
    this.candidate = voice ? this.candidate + input.length : 0;
    this.hangover = voice ? Math.ceil(sampleRate * .3) : Math.max(0, this.hangover - input.length);
    const speaking = this.hangover > 0;
    if (speaking !== this.speech) {
      this.speech = speaking;
      this.port.postMessage({type:"speech_activity", active:speaking});
    }

    if (this.mode === "local") {
      // Keep 500 ms BEFORE the first voiced threshold, plus the 60 ms needed
      // to confirm speech. The whole buffer still has the same 8 s ceiling.
      const keep = this.preroll + this.candidate;
      if (this.length + input.length > keep)
        this.drop(Math.min(this.length, this.length + input.length - keep));
    }
    if (this.length + input.length > this.capacity) {
      this.reset("failed");
      this.port.postMessage({type:"overflow"});
      return true;
    }
    for (let i = 0; i < input.length; i++) {
      const index = (this.head + this.length + i) % this.capacity;
      this.samples[index] = input[i];
      this.voiced[index] = voice ? 1 : 0;
    }
    this.length += input.length;
    if (this.mode === "local" && this.candidate >= sampleRate * .06) {
      this.mode = "opening";
      this.port.postMessage({type:"speech"});
    }
    if (this.mode !== "streaming" || !output) return true;

    // Catch up only inside a contiguous silence. Speech is never accelerated,
    // overwritten, repeated or truncated to hide a slow connection.
    const target = Math.ceil(sampleRate * .12);
    if (!this.protected && this.length > sampleRate * .35) {
      let silent = 0;
      const retain = Math.ceil(sampleRate * .24);
      const limit = Math.min(this.length, this.length - target + retain);
      while (silent < limit && !this.voiced[(this.head + silent) % this.capacity]) silent++;
      if (silent >= sampleRate * .3) this.drop(Math.min(silent - retain, this.length - target));
    }
    const count = Math.min(output.length, this.length);
    let emittedVoice = false;
    for (let i = 0; i < count; i++) {
      const index = (this.head + i) % this.capacity;
      output[i] = this.samples[index];
      emittedVoice ||= Boolean(this.voiced[index]);
    }
    this.drop(count);
    this.protected = Math.max(0, this.protected - count);
    if (emittedVoice && !this.sentSpeech) this.port.postMessage({type:"sent_speech"});
    this.sentSpeech = emittedVoice;
    return true;
  }
}
registerProcessor("jade-live-capture", JadeLiveCapture);
