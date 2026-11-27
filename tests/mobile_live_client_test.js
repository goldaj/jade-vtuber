/* Browser/server doubles: these checks do not open a microphone, use a
 * provider account, qualify echo cancellation or claim Android behaviour. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const code = fs.readFileSync(path.join(__dirname, "../src/jade_runtime/mobile_web/live-client.js"), "utf8");
const tick = () => new Promise(resolve => setImmediate(resolve));
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return {promise, resolve, reject};
}
function harness(options = {}) {
  let now = 0, nextTimer = 0, nextId = 0, amplitude = 0;
  const timers = new Map(), frames = new Map(), requests = [], sockets = [], peers = [], contexts = [], worklets = [];
  const order = [], tracks = [], states = [], transcripts = [], playbacks = [];
  let authFailures = 0;
  const server = {mode:options.mode || "live", revision:0, lease:"lease-1", autoAck:true, autoConnect:true,
    available:true, sound:true, permission:null, arm:null, create:null, close:null, session:0};
  const doc = {hidden:false};
  function track() {
    const value = {kind:"audio", stops:0, stop() { this.stops++; }};
    tracks.push(value);
    return value;
  }
  function stream() {
    const value = track();
    return {getTracks:() => [value], getAudioTracks:() => [value], track:value};
  }
  class Context {
    constructor() {
      order.push("audio-context"); contexts.push(this); this.state = "running"; this.destination = {speaker:true};
      this.audioWorklet = {addModule:async url => { assert.equal(url, "/assets/live-audio-worklet.js"); }};
    }
    resume() { return Promise.resolve(); }
    close() { this.state = "closed"; return Promise.resolve(); }
    createMediaStreamSource(source) {
      return {source, connections:[], connect(node) { this.connections.push(node); }, disconnect() { this.disconnected = true; }};
    }
    createMediaStreamDestination() { return {stream:stream()}; }
    createAnalyser() {
      return {fftSize:512, connect(node) { this.destination = node; }, disconnect() {},
        getFloatTimeDomainData(array) { array.fill(amplitude); }};
    }
  }
  class Worklet {
    constructor(context, name) {
      assert.equal(name, "jade-live-capture"); worklets.push(this); this.commands = [];
      this.port = {postMessage:event => this.commands.push(event)};
    }
    connect(destination) { this.destination = destination; }
    disconnect() {}
    emit(data) { this.port.onmessage?.({data}); }
  }
  class Peer {
    constructor() { peers.push(this); this.senders = []; this.connectionState = this.iceConnectionState = "new"; }
    addTrack(value, owner) {
      this.senders.push({track:value, owner, replaceTrack(track) { this.track = track; return Promise.resolve(); }});
    }
    getSenders() { return this.senders; }
    createDataChannel(name) {
      assert.equal(name, "oai-events");
      return this.channel = {sent:[], send(value) { this.sent.push(value); }, close() { this.closed = true; }};
    }
    async createOffer() { return {type:"offer", sdp:"private-offer"}; }
    async setLocalDescription(value) { this.localDescription = value; }
    async setRemoteDescription(value) {
      assert.equal(value.sdp, "private-answer"); this.remoteDescription = value;
      if (server.autoConnect) { this.connectionState = "connected"; this.onconnectionstatechange?.(); }
    }
    close() { this.closed = true; this.connectionState = "closed"; }
  }
  const baseState = () => ({mode:server.mode, revision:server.revision, lease_id:server.lease,
    lease_state:"armed", session_state:"absent", session_id:null});
  class Socket {
    constructor(url, protocol) {
      assert.equal(url, "wss://jade.test/api/live/control"); assert.equal(protocol, "jade-live-v1");
      sockets.push(this); this.readyState = 0; this.sent = [];
    }
    send(data) {
      const event = JSON.parse(data); this.sent.push(event);
      if (event.type === "heartbeat" && server.autoAck) this.emit({type:"state", seq:event.seq,
        ...baseState(), lease_state:this.draining ? "draining" : "armed",
        session_state:peers.at(-1) && !peers.at(-1).closed ? "active" : "absent",
        session_id:server.session ? "session-" + server.session : null});
    }
    open() { this.readyState = 1; this.onopen?.(); }
    emit(event) { this.onmessage?.({data:JSON.stringify(event)}); }
    ready() { this.open(); this.emit({type:"ready", state:baseState()}); }
    close() { this.readyState = 3; this.closed = true; }
  }
  function response(body, status = 200) { return {status, ok:status < 400, json:async () => body}; }
  const env = {document:doc, navigator:{mediaDevices:{async getUserMedia() {
    order.push("getUserMedia"); return server.permission ? server.permission.promise : stream();
  }}}, location:{protocol:"https:", host:"jade.test"}, isSecureContext:true,
  performance:{now:() => now}, crypto:{randomUUID:() => "opaque-" + (++nextId)},
  AudioContext:Context, AudioWorkletNode:Worklet, RTCPeerConnection:Peer, WebSocket:Socket, AbortController,
  requestAnimationFrame(fn) { const id = ++nextTimer; frames.set(id, fn); return id; },
  cancelAnimationFrame(id) { frames.delete(id); },
  setTimeout(fn, ms) { const id = ++nextTimer; timers.set(id, {fn, at:now + ms}); return id; },
  clearTimeout(id) { timers.delete(id); },
  setInterval(fn, ms) { const id = ++nextTimer; timers.set(id, {fn, at:now + ms, interval:ms}); return id; },
  clearInterval(id) { timers.delete(id); }, dispatchEvent() {},
  async fetch(url, options) {
    assert.equal(options.credentials, "omit"); assert.equal(options.cache, "no-store");
    assert.equal(options.headers.Authorization, "Bearer in-memory-owner-token");
    assert(!url.includes("token"));
    const body = options.body ? JSON.parse(options.body) : null;
    requests.push({url, body, options}); order.push(url);
    if (url === "/api/live/capabilities") {
      if (server.capabilities) return server.capabilities.promise;
      return response({enabled:true, available:server.available, reason:server.reason, reasons:server.reasons,
      heartbeat_seconds:2, lease_seconds:5, opening_timeout_seconds:8,
      ...(server.observed ? {state:server.observed} : {}),
      voice:{selected:"test-voice", notice:"Voix de test"}});
    }
    if (url === "/api/voice/preferences") {
      if (body) {
        if (body.revision !== server.revision) return response({error:"preference_conflict",
          preference:{mode:server.mode, revision:server.revision}}, 409);
        server.mode = body.mode; server.revision++;
      }
      return response({mode:server.mode, revision:server.revision});
    }
    if (url === "/api/live/arm") return server.arm ? server.arm.promise : response({...baseState(), heartbeat_seconds:2, lease_seconds:5});
    if (url === "/api/live/sessions") {
      server.session++;
      return server.create ? server.create.promise : response({sdp:"private-answer", session_id:"session-" + server.session});
    }
    if (url === "/api/live/sessions/close") {
      if (server.close) return server.close.promise;
      if (body.drain) { if (sockets.at(-1)) sockets.at(-1).draining = true;
        return response({...baseState(), lease_state:"draining", session_state:"active", session_id:"session-" + server.session}); }
      return response({...baseState(), lease_state:"closed", session_state:"absent"});
    }
    throw new Error("unexpected URL " + url);
  }};
  Object.assign(env, options.browser || {});
  const sandbox = {window:env, document:doc, navigator:env.navigator, performance:env.performance,
    AbortController, Event, console};
  vm.runInNewContext(code, sandbox);
  const client = env.JadeLive.create({environment:env, getToken:() => "in-memory-owner-token",
    getThread:() => "thread-1", getSoundEnabled:() => server.sound,
    onState:value => states.push(value), onTranscript:event => transcripts.push(event),
    onAuthFailure:() => { authFailures++; },
    onPlayback:(level, playing) => playbacks.push({level, playing})});
  async function selectLive() { await client.refresh(); assert.equal(await client.setMode("live"), true); }
  async function arm() {
    const promise = client.arm(); await tick();
    sockets.at(-1)?.ready();
    return promise;
  }
  async function advance(ms) {
    const target = now + ms;
    for (;;) {
      const due = [...timers].filter(([, value]) => value.at <= target).sort((a, b) => a[1].at - b[1].at)[0];
      if (!due) break;
      const [id, value] = due; now = value.at;
      if (value.interval) value.at += value.interval; else timers.delete(id);
      value.fn(); await tick();
    }
    now = target; await tick();
  }
  return {client, selectLive, arm, advance, server, sockets, peers, contexts, worklets, requests,
    order, tracks, transcripts, states, playbacks, stream, response, doc, timers, frames,
    get authFailures() { return authFailures; },
    audio(level) { amplitude = level; const pending = [...frames.values()]; frames.clear(); pending.forEach(fn => fn()); }};
}

(async () => {
  {
    const h = harness();
    assert.equal(await h.client.arm(), false, "the preference must be loaded before any microphone gesture can arm");
    await h.client.refresh();
    assert.equal(h.client.mode, "live", "a new owner's server default is immediately Live");
    assert.equal(h.client.state.loaded, true);
    assert(h.requests.every(value => value.body === null), "reading the default never writes a preference or creates a session");
    assert.equal(h.contexts.length, 0); assert.equal(h.tracks.length, 0);
    assert.equal(h.peers.length, 0); assert.equal(h.sockets.length, 0);
    assert.equal(await h.arm(), true, "Home may arm directly without selecting Live in Profile first");
    await h.client.stop("test_complete");
  }
  {
    const h = harness({mode:"classic"});
    await h.client.refresh(); await h.client.refresh();
    assert.equal(h.client.mode, "classic", "an explicit stored OFF is never replaced by the new default");
    assert.equal(await h.client.arm(), false);
    assert(h.requests.every(value => value.body === null));
    assert.equal(h.contexts.length, 0); assert.equal(h.tracks.length, 0);
  }
  {
    const h = harness({mode:"classic", browser:{AudioWorkletNode:undefined}});
    await h.client.refresh();
    assert.equal(h.client.state.supported, false); assert.equal(h.client.state.available, false);
    assert.match(h.client.state.availability_message, /navigateur.*WebRTC et AudioWorklet/);
    assert.equal(h.contexts.length, 0, "compatibility checks do not open audio");
    const insecure = harness({browser:{isSecureContext:false}});
    await insecure.client.refresh();
    assert.match(insecure.client.state.availability_message, /HTTPS/);
  }
  {
    const h = harness(); h.server.available = false;
    h.server.reason = "api_key_missing";
    h.server.reasons = ["api_key_missing", "live_disabled"];
    await h.client.refresh();
    assert.match(h.client.state.availability_message, /connexion OpenAI.*pas configurée/);
    assert.match(h.client.state.availability_message, /désactivé dans la configuration/);
    assert.equal(await h.client.arm(), false); assert.equal(h.contexts.length, 0);
    h.server.capabilities = deferred();
    const pending = h.client.refresh();
    h.server.capabilities.reject(new TypeError("private network error"));
    await pending;
    assert.match(h.client.state.availability_message, /Connexion à Jade impossible/);
    assert(!h.client.state.availability_message.includes("private"));
  }
  {
    let entropy = 0;
    const h = harness({browser:{crypto:{getRandomValues(bytes) { bytes.fill(++entropy); return bytes; }}}});
    await h.client.refresh(); await h.arm();
    h.worklets[0].emit({type:"speech"}); await tick();
    const arm = h.requests.find(value => value.url === "/api/live/arm");
    const open = h.requests.find(value => value.url === "/api/live/sessions");
    assert.match(arm.body.client_id, /^live-[0-9a-f]{32}$/);
    assert.match(open.body.request_id, /^[0-9a-f]{32}$/);
    assert.notEqual(arm.body.client_id.slice(5), open.body.request_id);
    await h.client.stop("test_complete");
    const unavailableCrypto = harness({browser:{crypto:undefined}});
    await unavailableCrypto.client.refresh();
    assert.equal(unavailableCrypto.client.state.loaded, true, "missing randomUUID never strands the initial UI");
    assert.equal(unavailableCrypto.contexts.length, 0);
  }
  for (const [code, status, expected] of [
    ["live_auth_failed", 401, /OpenAI refuse l’authentification/],
    ["live_access_denied", 403, /compte OpenAI.*pas accès/],
    ["live_model_unavailable", 404, /modèle Live.*pas disponible/],
    ["live_quota_exceeded", 429, /quota du compte OpenAI/],
    ["live_rate_limited", 429, /trop de demandes/],
    ["live_connection_failed", 503, /joindre OpenAI/],
    ["live_open_failed", 502, /ouvrir la conversation/],
  ]) {
    const h = harness(); await h.client.refresh(); await h.arm();
    h.server.create = deferred();
    h.worklets[0].emit({type:"speech"}); await tick();
    h.server.create.resolve(h.response({code, error:code, message:"private provider payload"}, status));
    await tick(); await tick();
    assert.match(h.client.state.message, expected, code);
    assert.equal(h.client.state.reason, code);
    assert.equal(h.authFailures, 0, "provider refusal cannot invalidate the owner's mobile login");
    assert.equal(h.tracks[0].stops, 1);
    assert.equal(h.requests.filter(value => value.url === "/api/live/sessions").length, 1);
    assert(!h.client.state.message.includes("private provider"));
  }
  {
    const h = harness(); await h.selectLive();
    assert.equal(h.contexts.length, 0, "the persisted ON choice must not create audio resources");
    assert.equal(h.sockets.length, 0); assert.equal(h.tracks.length, 0);
    assert.equal(await h.arm(), true);
    assert(h.order.indexOf("/api/live/arm") < h.order.indexOf("getUserMedia"), "exclusive lease precedes permission/capture");
    assert.equal(h.peers.length, 0, "a local armed microphone does not start a paid session before speech");
    assert.deepEqual(h.sockets[0].sent[0], {type:"auth", token:"in-memory-owner-token",
      client_id:"live-opaque-1", thread_id:"thread-1", lease_id:"lease-1"});
    h.worklets[0].emit({type:"speech"}); await tick();
    const first = h.peers[0];
    assert.equal(first.senders[0].owner, h.worklets[0].destination.stream,
      "WebRTC sends worklet output, never the unbuffered microphone track");
    assert.equal(first.channel.sent.length, 0, "frontend does not control provider sessions/responses");
    assert(h.worklets[0].commands.some(event => event.type === "connected"));
    first.ontrack({streams:[h.stream()]}); h.audio(.1);
    assert(h.playbacks.at(-1).level > 0);
    assert(h.sockets[0].sent.some(event => event.type === "playback" && event.state === "playing" && event.offset_ms === undefined));
    h.sockets[0].emit({type:"transcript", session_id:"stale-session", segment_id:"x", text:"old"});
    assert.equal(h.transcripts.length, 0);
    h.sockets[0].emit({type:"transcript", session_id:"session-1", segments:[{segment_id:"a", role:"assistant", text:"salut"}]});
    assert.equal(h.transcripts.length, 1);
    h.sockets[0].emit({type:"state", ...{mode:"live", revision:1, lease_id:"lease-1", lease_state:"armed",
      session_state:"absent", session_id:null}});
    assert.equal(first.closed, true); assert.equal(h.tracks[0].stops, 0);
    assert.equal(h.client.state.capture, "armed", "server idle releases only the remote generation");
    assert.equal(h.sockets[0].closed, undefined);
    assert.equal(h.worklets[0].commands.at(-1).type, "local");
    h.worklets[0].emit({type:"speech"}); await tick();
    assert.equal(h.peers.length, 2); assert.equal(h.client.state.session_id, "session-2");
    await h.client.stop("test_complete");
    assert.equal(h.tracks[0].stops, 1); assert.equal(h.contexts[0].state, "closed");
    assert.equal(h.frames.size, 0); assert.equal(h.timers.size, 0);
  }
  {
    const h = harness(); await h.selectLive(); h.server.permission = deferred();
    const pending = h.arm(); await tick(); await tick();
    assert(h.order.includes("getUserMedia"));
    await h.client.stop("background");
    const late = h.stream(); h.server.permission.resolve(late);
    assert.equal(await pending, false);
    assert.equal(late.track.stops, 1, "late permission cannot resurrect capture after background/stop");
    assert.equal(h.peers.length, 0); assert.equal(h.contexts[0].state, "closed");
  }
  {
    const h = harness(); await h.selectLive(); h.server.arm = deferred();
    const pending = h.client.arm(); await tick(); await h.client.stop("new_thread");
    h.server.arm.resolve(h.response({mode:"live", revision:1, lease_id:"late-lease", lease_state:"armed"}));
    assert.equal(await pending, false); await tick();
    assert(!h.order.includes("getUserMedia"));
    assert(h.requests.some(value => value.url.endsWith("/close") && value.body.lease_id === "late-lease"),
      "a lease granted after cancellation is explicitly released");
  }
  {
    const h = harness(); await h.selectLive(); await h.arm();
    h.worklets[0].emit({type:"speech"}); await tick();
    h.worklets[0].emit({type:"sent_speech"});
    await h.client.mute();
    assert.equal(h.tracks[0].stops, 1); assert.equal(h.client.state.lease_state, "draining");
    assert.equal(h.contexts[0].state, "running", "mute stops capture immediately while preserving the bounded reply");
    assert.equal(h.peers[0].closed, undefined);
    await h.advance(14000);
    h.sockets[0].emit({type:"transcript", session_id:"session-1", text:"late reply"});
    await h.advance(1000);
    assert.equal(h.peers[0].closed, true); assert.equal(h.contexts[0].state, "closed");
    assert(h.requests.some(value => value.body?.reason === "drain_timeout"), "new activity cannot extend the 15 s deadline");
    assert.equal(h.client.state.message, "", "a completed drain cannot still announce that Jade is finishing her reply");
  }
  for (const diagnostic of [null, "live_rate_limited"]) {
    const h = harness(); await h.client.refresh(); await h.arm();
    h.worklets[0].emit({type:"speech"}); await tick();
    h.worklets[0].emit({type:"sent_speech"}); await h.client.mute();
    if (diagnostic) h.sockets[0].emit({type:"incident", code:diagnostic, fatal:false});
    h.sockets[0].emit({type:"state", mode:"live", revision:0, lease_id:"lease-1",
      lease_state:"closed", session_state:"absent", session_id:null});
    assert.equal(h.client.state.active, false); assert.equal(h.client.state.session_state, "absent");
    assert.equal(h.contexts[0].state, "closed"); assert.equal(h.timers.size, 0);
    if (diagnostic) assert.match(h.client.state.message, /trop de demandes/,
      "finishing a drain preserves a provider diagnostic");
    else assert.equal(h.client.state.message, "", "provider completion removes the transient drain guidance too");
  }
  {
    const h = harness(); await h.selectLive(); await h.arm(); h.server.autoAck = false;
    await h.advance(2000);
    h.sockets[0].emit({type:"state", seq:1});
    await h.advance(4000);
    h.sockets[0].emit({type:"state", seq:1});
    await h.advance(1000);
    assert.equal(h.tracks[0].stops, 1, "replaying an old ACK cannot keep an unobserved microphone alive");
    assert.equal(h.client.state.reason, "heartbeat_timeout");
  }
  {
    const h = harness(); await h.selectLive(); await h.arm();
    h.sockets[0].emit({type:"preference", mode:"classic", revision:2}); await tick();
    assert.equal(h.tracks[0].stops, 1); assert.equal(h.client.mode, "classic");
    // Old owner preference read arriving after OFF must not restore Live.
    h.server.mode = "live"; h.server.revision = 1; await h.client.refresh();
    assert.equal(h.client.mode, "classic");
    assert.equal(h.client.state.revision, 2); assert.equal(h.peers.length, 0);
  }
  {
    const h = harness(); await h.selectLive(); await h.arm(); h.server.create = deferred();
    h.worklets[0].emit({type:"speech"}); await tick();
    await h.client.stop("text");
    h.server.create.resolve(h.response({session_id:"session-1", sdp:"private-answer"})); await tick();
    assert.equal(h.peers[0].remoteDescription, undefined, "late SDP cannot reattach stopped media");
    assert.equal(h.peers[0].closed, true);
    assert(!h.worklets[0].commands.some(event => event.type === "connected"));
  }
  {
    const h = harness(); await h.selectLive(); await h.arm(); h.server.autoConnect = false;
    h.worklets[0].emit({type:"speech"}); await tick();
    await h.advance(8000);
    assert.equal(h.client.state.reason, "opening_timeout"); assert.equal(h.tracks[0].stops, 1);
    assert.equal(h.peers[0].closed, true);
  }
  {
    const h = harness(); await h.selectLive(); h.server.sound = false;
    assert.equal(await h.client.arm(), false); assert.equal(h.contexts.length, 0);
    h.server.sound = true; assert.equal(h.contexts.length, 0, "restoring sound never rearms capture by itself");
    await h.arm(); h.worklets[0].emit({type:"overflow"}); await tick();
    assert.equal(h.tracks[0].stops, 1); assert.equal(h.client.state.reason, "buffer_overflow");
    assert.equal(h.peers.length, 0, "overflow is an explicit failure, not a classic fallback/replay");
  }
  {
    const h = harness(); await h.selectLive(); await h.arm();
    h.worklets[0].port.postMessage = () => { throw new Error("worklet already failed"); };
    await h.client.stop("device_error");
    assert.equal(h.tracks[0].stops, 1, "physical tracks are revoked even if worklet teardown throws");
    assert.equal(h.contexts[0].state, "closed");
  }
  {
    const h = harness(); await h.selectLive(); await h.arm();
    h.sockets[0].emit({type:"state", mode:"live", revision:1, lease_id:"lease-1",
      lease_state:"closed", session_state:"opening_unknown", reason:"creation_unconfirmed"});
    assert.equal(h.tracks[0].stops, 1); assert.equal(h.client.state.available, false);
    assert.equal(h.client.state.session_state, "opening_unknown");
    assert.equal(await h.client.arm(), false, "unknown provider creation needs reconciliation before another attempt");
    h.server.observed = {lease_state:"closed", session_state:"absent", session_id:null};
    await h.client.refresh();
    assert.equal(h.client.state.session_state, "absent");
    assert.equal(h.client.state.available, true);
    assert.equal(h.client.state.capture, "closed", "reconciliation never rearms the microphone");
  }
  console.log("Mobile Live client: lifecycle, leases, WebRTC source, replay guards and bounded drain PASS (doubles only)");
})().catch(error => { console.error(error); process.exitCode = 1; });
