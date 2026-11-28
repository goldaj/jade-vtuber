/* Resample Jade's decoded WebRTC output entirely in a bounded PCM ring.
 * The fractional read position raises speed and pitch together. */
"use strict";

class JadeLiveOutput extends AudioWorkletProcessor {
  constructor({processorOptions = {}} = {}) {
    super();
    const speed = processorOptions.speed ?? 1.10;
    this.speed = Number.isFinite(speed) && speed >= 1 && speed <= 1.25 ? speed : 1.10;
    this.preroll = Math.ceil(sampleRate * .020);
    this.startReserve = Math.ceil(sampleRate * .240);
    this.fastReserve = Math.ceil(sampleRate * .140);
    this.lowReserve = Math.ceil(sampleRate * .040);
    this.endSilence = Math.ceil(sampleRate * .300);
    this.tailFade = Math.ceil(sampleRate * .003);
    this.samples = new Float32Array(Math.ceil(sampleRate * .750));
    this.state = "idle";
    this.stopped = false;
    this.reset();
    this.port.onmessage = ({data}) => {
      if (data?.type === "stop") {
        this.stopped = true;
        this.reset();
      } else if (data?.type === "reset" && !this.stopped) {
        this.reset();
      } else if (data?.type === "drain" && !this.stopped) {
        this.draining = true;
        this.ending = true;
        if (this.state === "idle") this.finish();
      }
    };
  }

  setState(state) {
    if (state === this.state) return;
    this.state = state;
    this.port.postMessage({type:"state", state});
  }

  reset() {
    this.samples.fill(0);
    this.head = this.size = this.position = this.quiet = 0;
    this.rate = this.speed;
    this.ending = this.draining = false;
    this.setState("idle");
  }

  discard(count) {
    const end = this.head + count;
    this.samples.fill(0, this.head, Math.min(end, this.samples.length));
    if (end > this.samples.length) this.samples.fill(0, 0, end - this.samples.length);
    this.head = end % this.samples.length;
    this.size -= count;
  }

  append(input, start = 0) {
    if (this.size + input.length - start > this.samples.length) {
      // Equal-size Web Audio input/output blocks cannot reach this bound
      // during normal playback. Hand unexpected input back to the client.
      this.reset();
      this.stopped = true;
      this.port.postMessage({type:"overflow"});
      return;
    }
    let write = (this.head + this.size) % this.samples.length;
    for (let index = start; index < input.length; index++) {
      this.samples[write] = input[index];
      if (++write === this.samples.length) write = 0;
    }
    this.size += input.length - start;
  }

  ingest(input, outputLength) {
    if (!input?.length) {
      this.quiet += outputLength;
      this.ending = this.quiet >= this.endSilence;
      return;
    }
    let power = 0;
    for (const sample of input) power += sample * sample;
    const voiced = power >= input.length * .002 ** 2;
    if (this.state === "idle") {
      if (!voiced) {
        const start = Math.max(0, input.length - this.preroll);
        this.discard(Math.max(0, this.size + input.length - start - this.preroll));
        this.append(input, start);
        return;
      }
      this.setState("buffering");
    }
    // Retain quiet syllables and pauses. When input stays quiet for 300 ms,
    // let the current response drain without appending unlimited silence.
    if (voiced) this.quiet = 0;
    if (this.quiet < this.endSilence) this.append(input);
    if (!voiced) this.quiet += input.length;
    this.ending = this.quiet >= this.endSilence;
  }

  finish() {
    this.discard(this.size);
    this.position = this.quiet = 0;
    this.rate = this.speed;
    this.ending = false;
    this.setState(this.draining ? "drained" : "idle");
  }

  render(output) {
    const available = this.size - this.position;
    const reserve = available - output.length;
    // Consume the prebuffer at full speed, then ease toward the incoming
    // rate before it runs out. At a known end there's no input to wait for.
    const fraction = this.ending ? 1 : Math.max(0, Math.min(1,
      (reserve - this.lowReserve) / (this.fastReserve - this.lowReserve)));
    const target = 1 + (this.speed - 1) * fraction;
    const duration = output.length / sampleRate;
    const nextRate = this.rate + (target - this.rate) * (1 - Math.exp(-duration / .040));
    const rateStep = (nextRate - this.rate) / output.length;
    let position = this.position;
    let rate = this.rate;
    for (let frame = 0; frame < output.length && position < this.size; frame++) {
      const index = Math.floor(position);
      const fraction = position - index;
      if (fraction && index + 1 === this.size && !this.ending) break;
      const left = this.samples[(this.head + index) % this.samples.length];
      const right = index + 1 < this.size
        ? this.samples[(this.head + index + 1) % this.samples.length] : left;
      const gain = this.ending ? Math.min(1, (this.size - position) / this.tailFade) : 1;
      output[frame] = gain * (left + (right - left) * fraction);
      position += rate;
      rate += rateStep;
    }
    const consumed = Math.min(this.size, Math.floor(position));
    this.discard(consumed);
    this.position = position - consumed;
    this.rate = nextRate;
  }

  process(inputs, outputs) {
    const output = outputs[0]?.[0];
    if (output) output.fill(0);
    if (this.stopped) return false;
    if (!output?.length || this.state === "drained") return true;
    if (!this.draining) this.ingest(inputs[0]?.[0], output.length);
    if (this.stopped) return false;
    if (this.state === "buffering" && (this.size >= this.startReserve || this.ending)) {
      this.setState("playing");
    }
    if (this.state === "playing") {
      this.render(output);
      if (this.ending && this.size === 0) this.finish();
    }
    return true;
  }
}

registerProcessor("jade-live-output", JadeLiveOutput);
