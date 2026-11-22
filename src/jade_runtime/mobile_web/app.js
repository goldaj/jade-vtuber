/* Jade owner-only phone client. No cookies, localStorage, sessionStorage,
 * analytics, third-party servers, remote libraries or alternative AI engines.
 * Speech recognition is performed by Jade's existing OpenAI STT on the PC.
 */
"use strict";
(() => {
  const $ = (id) => document.getElementById(id);
  const form = $("composer"), input = $("message"), log = $("messages");
  const mic = $("mic"), send = $("send"), status = $("status");
  const modal = $("auth-modal"), authForm = $("auth-form"), authInput = $("auth-token");
  const connection = $("connection-status"), soundToggle = $("sound-toggle");
  const newChat = $("new-chat");
  const linkForm = $("identity-link-form"), linkResult = $("identity-result");
  const linkCopy = $("identity-copy");
  let linkCommand = "";
  let linkPending = false;
  const avatar = () => window.JadeAvatar || {setMouth() {}, setIntent() {}, setSpeaking() {}, resetIntent() {}};
  let token = "";
  let busy = false;
  let recording = null;
  let starting = false;
  let soundEnabled = true;
  let audioContext = null;
  let playing = null;
  let playFrame = null;
  let streamController = null;
  let activeDuplex = null;
  const streamSources = new Set();
  let streamAnalyser = null;
  let streamNextTime = 0;
  let thread = newThread();

  function newThread() {
    // The opaque session is not identity/authentication. Only the Tailscale
    // connection and the API bearer token authenticate Goldaj's private client.
    if (window.crypto && crypto.randomUUID) return "m-" + crypto.randomUUID().replace(/-/g, "").slice(0, 24);
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    return "m-" + Array.from(bytes, b => b.toString(16).padStart(2,"0")).join("");
  }

  function setStatus(message, working = false) {
    status.textContent = message;
    send.disabled = working;
    newChat.disabled = working;
    input.disabled = working;
    mic.disabled = working && !recording && !activeDuplex;
  }

  function authorizeAgain() {
    token = "";
    linkCommand = "";
    linkResult.textContent = "";
    linkCopy.disabled = true;
    authInput.value = "";
    modal.classList.remove("hidden");
    connection.classList.remove("online");
    connection.textContent = "Hors connexion";
    setStatus("Accès expiré : ressaisis ton jeton.");
    authInput.focus();
  }

  function addBubble(text, kind, when = new Date()) {
    const entry = document.createElement("article");
    entry.className = "bubble " + kind;
    // textContent is intentional; model/user input cannot inject HTML.
    const content = document.createElement("span");
    content.textContent = text;
    const info = document.createElement("small");
    info.textContent = (kind === "jade" ? "Jade" : "Goldaj") + " · " +
      when.toLocaleTimeString("fr-FR", {hour:"2-digit",minute:"2-digit"});
    entry.append(content, info);
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
    return entry;
  }

  function addJadeReply(text, files) {
    const entry = addBubble(text, "jade");
    for (const item of Array.isArray(files) ? files.slice(0, 4) : []) {
      if (!item || !/^\\/api\\/documents\\/[a-f0-9]{32}$/.test(item.url)) continue;
      const control = document.createElement("button");
      control.type = "button";
      control.className = "attachment-button";
      control.textContent = "Télécharger " + item.name + " · 24 h";
      control.addEventListener("click", async () => {
        if (!token) { authorizeAgain(); return; }
        control.disabled = true;
        try {
          const response = await fetch(item.url, {method:"GET", mode:"same-origin",
            credentials:"omit", cache:"no-store",
            headers:{"Authorization":"Bearer " + token}});
          if (response.status === 401) { authorizeAgain(); return; }
          if (!response.ok) throw new Error("Pièce jointe expirée ou indisponible.");
          const url = URL.createObjectURL(await response.blob());
          const link = document.createElement("a");
          link.href = url;
          link.download = item.name;
          document.body.appendChild(link);
          link.click();
          link.remove();
          setTimeout(() => URL.revokeObjectURL(url), 10000);
        } catch (error) {
          setStatus(error.message || "Téléchargement impossible.");
        } finally {
          control.disabled = false;
        }
      });
      entry.appendChild(control);
    }
    return entry;
  }

  function setReplyIntent(intent) {
    avatar().setIntent(intent || "neutral");
  }

  async function makeRequest(path, body, extraHeaders) {
    const headers = Object.assign({"Authorization":"Bearer " + token}, extraHeaders);
    const response = await fetch(path, {
      method: "POST", mode: "same-origin", credentials: "omit",
      cache: "no-store", headers, body
    });
    if (response.status === 401) {
      authorizeAgain();
      throw new Error("Jeton mobile incorrect : ressaisis-le.");
    }
    if (response.status === 403) {
      throw new Error("Accès réservé au propriétaire Tailscale : vérifie ton VPN et ton identité.");
    }
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      const messages = {
        429: "Jade est occupée. Réessaie dans quelques instants.",
        504: "La réponse a pris trop de temps."
      };
      throw new Error(result.message || messages[response.status] || result.error || "Erreur de communication avec Jade.");
    }
    connection.textContent = "Connectée à Jade";
    connection.classList.add("online");
    return result;
  }

  function ensureAudioContext() {
    if (!audioContext) {
      const AudioConstructor = window.AudioContext || window.webkitAudioContext;
      if (!AudioConstructor) throw new Error("La lecture audio n'est pas prise en charge.");
      audioContext = new AudioConstructor();
    }
    return audioContext.resume().then(() => audioContext);
  }

  function stopPlayback() {
    if (playFrame) cancelAnimationFrame(playFrame);
    playFrame = null;
    if (playing) {
      try { playing.stop(); } catch (_) {}
      playing = null;
      avatar().setSpeaking(false);
    }
    for (const source of streamSources) {
      try { source.stop(); } catch (_) {}
    }
    streamSources.clear();
    if (streamAnalyser) { streamAnalyser.disconnect(); streamAnalyser = null; }
    streamNextTime = 0;
    avatar().setSpeaking(false);
    avatar().setMouth(0);
  }

  function abortMobileStream() {
    if (streamController) streamController.abort();
  }

  function createMobileAudioTiming(transport) {
    const startedAt = performance.now();
    let firstReceivedAt = null, firstScheduledAt = null;
    return {
      received() {
        if (firstReceivedAt === null) firstReceivedAt = performance.now();
      },
      scheduled(when) {
        if (firstScheduledAt === null && typeof when === "number") firstScheduledAt = when;
      },
      done() {
        const endedAt = performance.now();
        const ms = value => value === null ? null : Math.round(value - startedAt);
        console.info("jade.mobile.audio", JSON.stringify({
          event: "rec029_mobile_pcm_client", transport,
          first_pcm_received_ms: ms(firstReceivedAt),
          first_play_scheduled_ms: ms(firstScheduledAt),
          stream_finished_ms: ms(endedAt),
          play_scheduled_before_stream_finished:
            firstScheduledAt === null ? null : firstScheduledAt < endedAt
        }));
      }
    };
  }

  async function playPcm(base64Audio, rate) {
    if (!soundEnabled || document.hidden) return null;
    if (rate !== 24000 || base64Audio.length > 12000) throw new Error("Fragment audio invalide.");
    const binary = atob(base64Audio);
    if (!binary.length || binary.length % 2) throw new Error("Fragment audio incomplet.");
    const context = await ensureAudioContext();
    const buffer = context.createBuffer(1, binary.length / 2, rate);
    const samples = buffer.getChannelData(0);
    for (let i = 0; i < samples.length; i++) {
      let value = binary.charCodeAt(i * 2) | (binary.charCodeAt(i * 2 + 1) << 8);
      if (value >= 32768) value -= 65536;
      samples[i] = value / 32768;
    }
    if (!streamAnalyser) {
      streamAnalyser = context.createAnalyser();
      streamAnalyser.fftSize = 1024;
      streamAnalyser.connect(context.destination);
      const analyser = streamAnalyser, data = new Uint8Array(analyser.fftSize);
      const animate = () => {
        if (streamAnalyser !== analyser) return;
        analyser.getByteTimeDomainData(data);
        let sum = 0;
        for (const value of data) sum += ((value - 128) / 128) ** 2;
        avatar().setMouth(Math.min(1, Math.sqrt(sum / data.length) * 7));
        playFrame = requestAnimationFrame(animate);
      };
      animate();
    }
    const source = context.createBufferSource();
    source.buffer = buffer;
    source.connect(streamAnalyser);
    streamSources.add(source);
    const start = Math.max(context.currentTime + 0.05, streamNextTime);
    streamNextTime = start + buffer.duration;
    avatar().setSpeaking(true);
    source.onended = () => {
      streamSources.delete(source);
      source.disconnect();
      if (!streamSources.size) {
        if (streamAnalyser) streamAnalyser.disconnect();
        streamAnalyser = null;
        if (playFrame) cancelAnimationFrame(playFrame);
        playFrame = null;
        avatar().setMouth(0);
        avatar().setSpeaking(false);
      }
    };
    const scheduledAt = performance.now() + Math.max(0, start - context.currentTime) * 1000;
    source.start(start);
    return scheduledAt;
  }

  async function makeStreamingRequest(path, body, extraHeaders) {
    // Choose the legacy format before sending anything: retrying afterward
    // could produce a second billable conversation and voice synthesis.
    if (typeof ReadableStream === "undefined" || typeof TextDecoder === "undefined" ||
        typeof AbortController === "undefined") {
      await present(await makeRequest(path, body, extraHeaders));
      return;
    }
    const controller = new AbortController();
    streamController = controller;
    try {
      const headers = Object.assign({"Authorization":"Bearer " + token, "X-Jade-Stream":"1"}, extraHeaders);
      const response = await fetch(path, {method:"POST", mode:"same-origin", credentials:"omit",
        cache:"no-store", headers, body, signal:controller.signal});
      if (response.status === 401) { authorizeAgain(); throw new Error("Jeton mobile incorrect : ressaisis-le."); }
      if (response.status === 403) throw new Error("Accès réservé au propriétaire Tailscale.");
      if (!response.ok) {
        const result = await response.json().catch(() => ({}));
        throw new Error(result.message || result.error || "Erreur de communication avec Jade.");
      }
      if (!response.body) throw new Error("La lecture progressive est indisponible sur ce navigateur.");
      connection.textContent = "Connectée à Jade";
      connection.classList.add("online");
      const reader = response.body.getReader(), decoder = new TextDecoder();
      let pending = "", receivedReply = false, done = false, audioFailed = false;
      let audioFailureReason = null;
      const audioTiming = createMobileAudioTiming("http_ndjson");
      async function consume(line) {
        const event = JSON.parse(line);
        if (event.type === "reply") {
          if (receivedReply) throw new Error("Réponse multiple inattendue.");
          receivedReply = true;
          if (event.transcript) addBubble(event.transcript, "me");
          addJadeReply(String(event.reply || "…"), event.attachments);
          setReplyIntent(event.intent);
        } else if (event.type === "pcm") {
          if (!receivedReply) throw new Error("Audio reçu avant la réponse.");
          audioTiming.received();
          try { audioTiming.scheduled(await playPcm(event.pcm_b64, event.sample_rate)); }
          catch (_) { audioFailed = true; }
        } else if (event.type === "wav") {
          if (!receivedReply) throw new Error("Audio reçu avant la réponse.");
          if (soundEnabled && !(await playWav(event.audio_wav_b64))) audioFailed = true;
        } else if (event.type === "audio_error") {
          audioFailed = true;
          audioFailureReason = event.incident_code || null;
        }
        else if (event.type === "done") { done = true; audioTiming.done(); }
        else throw new Error("Réponse audio inattendue.");
      }
      while (true) {
        const part = await reader.read();
        pending += decoder.decode(part.value || new Uint8Array(), {stream:!part.done});
        if (pending.length > 10_000_000) throw new Error("Réponse audio trop volumineuse.");
        let newline;
        while ((newline = pending.indexOf("\n")) !== -1) {
          const line = pending.slice(0, newline); pending = pending.slice(newline + 1);
          if (line) await consume(line);
        }
        if (part.done) break;
      }
      if (pending || !done || !receivedReply) throw new Error("Réponse audio interrompue.");
      setStatus(audioFailed && soundEnabled ? audioUnavailableStatus(audioFailureReason) : "Prête.");
    } finally {
      if (streamController === controller) streamController = null;
    }
  }

  async function playWav(base64Audio) {
    stopPlayback();
    if (!base64Audio || !soundEnabled || document.hidden) return true;
    try {
      const context = await ensureAudioContext();
      // Limit the size of an untrusted API response.
      if (base64Audio.length > 10_000_000) throw new Error("audio too large");
      const binary = atob(base64Audio);
      const bytes = Uint8Array.from(binary, c => c.charCodeAt(0));
      const decoded = await context.decodeAudioData(bytes.buffer.slice(0));
      const src = context.createBufferSource();
      src.buffer = decoded;
      const analyser = context.createAnalyser();
      analyser.fftSize = 1024;
      src.connect(analyser);
      analyser.connect(context.destination);
      playing = src;
      avatar().setSpeaking(true);
      src.onended = () => {
        if (playing === src) {
          playing = null;
          if (playFrame) cancelAnimationFrame(playFrame);
          playFrame = null;
          avatar().setMouth(0);
          avatar().setSpeaking(false);
        }
      };
      const samples = new Uint8Array(analyser.fftSize);
      function animateMouth() {
        if (playing !== src) return;
        analyser.getByteTimeDomainData(samples);
        let sum = 0;
        for (let i = 0; i < samples.length; i++) {
          const value = (samples[i] - 128) / 128;
          sum += value * value;
        }
        const volume = Math.sqrt(sum / samples.length);
        avatar().setMouth(Math.min(1, Math.max(0, volume * 7)));
        playFrame = requestAnimationFrame(animateMouth);
      }
      src.start(0);
      animateMouth();
      return true;
    } catch (_) {
      avatar().setMouth(0);
      return false;
    }
  }

  function audioUnavailableStatus(code) {
    if (code === "timeout") return "Réponse écrite reçue, mais la synthèse vocale a dépassé son délai.";
    if (code === "connection") return "Réponse écrite reçue, mais la connexion au service vocal a échoué.";
    if (code === "provider_limit") return "Réponse écrite reçue, mais le service vocal est temporairement limité.";
    if (code === "permission") return "Réponse écrite reçue, mais le service vocal n'est pas autorisé.";
    return "Réponse écrite reçue, mais la voix est indisponible.";
  }

  async function present(result) {
    if (result.transcript) addBubble(result.transcript, "me");
    addJadeReply(String(result.reply || "…"), result.attachments);
    setReplyIntent(result.intent);
    if (result.audio_wav_b64 && soundEnabled) {
      const played = await playWav(result.audio_wav_b64);
      if (!played) {
        setStatus("Réponse écrite reçue, mais la lecture audio a échoué.");
        return;
      }
    } else if (result.audio_unavailable && soundEnabled) {
      setStatus(audioUnavailableStatus(result.audio_unavailable_reason?.incident_code));
      return;
    }
    setStatus("Prête.");
  }

  async function submitText(event) {
    event.preventDefault();
    if (busy || recording || starting) return;
    if (!token) { authorizeAgain(); return; }
    const text = input.value.trim();
    if (!text) return;
    busy = true;
    stopPlayback();
    setStatus("Jade réfléchit…", true);
    // Unlock audio during user gesture, before the asynchronous fetch.
    if (soundEnabled) ensureAudioContext().catch(() => {});
    addBubble(text, "me");
    input.value = "";
    try {
      await makeStreamingRequest("/api/chat",
        JSON.stringify({text, session:thread, speak:soundEnabled}),
        {"Content-Type":"application/json"});
    } catch (error) {
      setStatus(error.message || "Impossible de joindre Jade.");
    } finally {
      busy = false;
      send.disabled = false;
      newChat.disabled = false;
      input.disabled = false;
      mic.disabled = false;
      input.focus();
    }
  }

  // Capture raw PCM with WebAudio, downsample to a short 16 kHz PCM16 WAV.
  // The frames stay in RAM and are discarded immediately after sending.
  function buildWav(chunks, sampleRate, totalFrames) {
    if (!totalFrames) throw new Error("Aucun son enregistré.");
    const pcm = new Float32Array(totalFrames);
    let offset = 0;
    for (const part of chunks) { pcm.set(part, offset); offset += part.length; }
    const ratio = sampleRate / 16000;
    const length = Math.min(320000, Math.floor(totalFrames / ratio));
    if (!length) throw new Error("Enregistrement trop court.");
    const out = new ArrayBuffer(44 + 2 * length);
    const view = new DataView(out);
    const label = (pos, text) => {
      for (let j = 0; j < text.length; j++) view.setUint8(pos + j, text.charCodeAt(j));
    };
    label(0, "RIFF"); view.setUint32(4, out.byteLength - 8, true);
    label(8, "WAVE"); label(12, "fmt ");
    view.setUint32(16, 16, true); view.setUint16(20, 1, true);
    view.setUint16(22, 1, true); view.setUint32(24, 16000, true);
    view.setUint32(28, 32000, true); view.setUint16(32, 2, true);
    view.setUint16(34, 16, true); label(36, "data");
    view.setUint32(40, length * 2, true);
    for (let i = 0; i < length; i++) {
      const start = Math.floor(i * ratio);
      const end = Math.min(totalFrames, Math.max(start + 1, Math.floor((i + 1) * ratio)));
      let average = 0;
      for (let j = start; j < end; j++) average += pcm[j];
      const sample = Math.max(-1, Math.min(1, average / (end - start)));
      view.setInt16(44 + 2 * i, sample < 0 ? sample * 32768 : sample * 32767, true);
    }
    return new Blob([out], {type:"audio/wav"});
  }

  async function startRecording() {
    if (!token) { authorizeAgain(); return; }
    if (busy || recording || starting) return;
    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus("Microphone indisponible : ouvrir l'application en HTTPS via Tailscale.");
      return;
    }
    stopPlayback();
    if (activeDuplex) { activeDuplex.cancel(); activeDuplex = null; }
    // Android may auto-stop after 20 seconds (no further user gesture).
    // Unlock the output context on the initial microphone tap too.
    if (soundEnabled) ensureAudioContext().catch(() => {});
    starting = true;
    mic.disabled = true;
    setStatus("Autorisation du microphone…");
    let stream, context;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {echoCancellation:true, noiseSuppression:true, autoGainControl:true},
        video: false
      });
      const Ctx = window.AudioContext || window.webkitAudioContext;
      context = new Ctx();
      await context.resume();
      if (document.hidden) throw new Error("la page est en arrière-plan");
      const source = context.createMediaStreamSource(stream);
      const processor = context.createScriptProcessor(4096, 1, 1);
      const silent = context.createGain();
      silent.gain.value = 0;
      const chunks = [];
      let frames = 0;
      let duplex = null;
      const duplexTiming = createMobileAudioTiming("websocket");
      if (window.JadeDuplex?.supported()) {
        duplex = window.JadeDuplex.create({
          token, session:thread, speak:soundEnabled,
          onEvent:async event => {
            if (event.type === "reply") {
              if (event.transcript) addBubble(event.transcript, "me");
              addJadeReply(String(event.reply || "…"), event.attachments);
              setReplyIntent(event.intent);
            } else if (event.type === "pcm") {
              duplexTiming.received();
              duplexTiming.scheduled(await playPcm(event.pcm_b64, event.sample_rate));
            } else if (event.type === "wav") {
              if (soundEnabled) await playWav(event.audio_wav_b64);
            } else if (event.type === "audio_error") {
              setStatus("Réponse écrite reçue, mais la voix est indisponible.");
            } else if (event.type === "done") {
              duplexTiming.done();
              setStatus("Prête.");
            }
          }
        });
        activeDuplex = duplex;
      }
      processor.onaudioprocess = event => {
        if (!recording || recording.context !== context) return;
        const sample = event.inputBuffer.getChannelData(0);
        if (frames >= context.sampleRate * 20) {
          stopRecording();
          return;
        }
        const part = new Float32Array(sample);
        chunks.push(part);
        frames += part.length;
        // Lightweight local end-of-utterance detection: after meaningful
        // speech, 1.2s of silence finalizes the utterance. Manual stop stays.
        let energy = 0;
        for (let n = 0; n < sample.length; n++) energy += sample[n] * sample[n];
        const loudness = Math.sqrt(energy / Math.max(1, sample.length));
        const now = Date.now();
        if (loudness > 0.024) {
          recording.voiceDetected = true;
          recording.lastVoiceAt = now;
        } else if (recording.voiceDetected && now - recording.lastVoiceAt > 1200
                   && now - recording.started > 800) {
          stopRecording();
          return;
        }
        if (duplex) {
          try { duplex.push(part, context.sampleRate); }
          catch (error) {
            if (recording) recording.duplexFailed = error;
            duplex.cancel();
            stopRecording();
          }
        }
      };
      source.connect(processor);
      processor.connect(silent);
      silent.connect(context.destination);
      recording = {stream, context, source, processor, silent, chunks, duplex,
                   voiceDetected:false, lastVoiceAt:0,
                   get frames() {return frames;}, started:Date.now()};
      mic.classList.add("recording");
      mic.setAttribute("aria-pressed", "true");
      mic.setAttribute("aria-label", "Arrêter et envoyer le message vocal");
      setStatus("J'enregistre ta voix… Touche le micro pour envoyer.");
      // Avoid leaving the microphone open after 20 seconds.
      recording.timer = setTimeout(stopRecording, 20000);
    } catch (_) {
      if (activeDuplex) { activeDuplex.cancel(); activeDuplex = null; }
      if (stream) stream.getTracks().forEach(track => track.stop());
      if (context) await context.close().catch(() => {});
      setStatus("Accès au micro refusé ou indisponible.");
    } finally {
      starting = false;
      mic.disabled = false;
    }
  }

  function resetMicButton() {
    mic.classList.remove("recording");
    mic.setAttribute("aria-pressed", "false");
    mic.setAttribute("aria-label", "Démarrer l'enregistrement vocal");
  }

  async function releaseRecording(current) {
    clearTimeout(current.timer);
    current.processor.onaudioprocess = null;
    for (const node of [current.source, current.processor, current.silent]) {
      try { node.disconnect(); } catch (_) {}
    }
    current.stream.getTracks().forEach(track => track.stop());
    await current.context.close().catch(() => {});
  }

  function cancelRecording() {
    const current = recording;
    if (!current) return;
    recording = null;
    resetMicButton();
    // Backgrounding the app must discard, never send, microphone data.
    if (current.duplex) current.duplex.cancel();
    if (activeDuplex === current.duplex) activeDuplex = null;
    releaseRecording(current).catch(() => {});
    setStatus("Enregistrement interrompu, aucun audio envoyé.");
  }

  async function stopRecording() {
    const current = recording;
    if (!current || busy) return;
    recording = null;
    busy = true;  // Prevent a second tap/turn while audio tracks are closing.
    // Unlock playback inside the stop-button gesture, before network awaits.
    if (soundEnabled) ensureAudioContext().catch(() => {});
    resetMicButton();
    setStatus("Je transmets ta voix à Jade…", true);
    const rate = current.context.sampleRate, frames = current.frames;
    try {
      await releaseRecording(current);
      if (Date.now() - current.started < 250 || frames < 4000) {
        if (current.duplex) current.duplex.cancel();
        setStatus("Enregistrement trop court.");
        return;
      }
      if (current.duplexFailed) throw current.duplexFailed;
      if (current.duplex) {
        try {
          await current.duplex.finish();
        } catch (error) {
          // Before the authenticated WebSocket was ready, STT never started.
          // Once ready, NEVER retry: that could charge for a second response.
          if (current.duplex.ready) throw error;
          const wav = buildWav(current.chunks, rate, frames);
          await makeStreamingRequest("/api/voice", wav, {
            "Content-Type":"audio/wav",
            "X-Jade-Session":thread,
            "X-Jade-Speak":soundEnabled ? "1" : "0"
          });
        }
      } else {
        const wav = buildWav(current.chunks, rate, frames);
        await makeStreamingRequest("/api/voice", wav, {
          "Content-Type":"audio/wav",
          "X-Jade-Session": thread,
          "X-Jade-Speak": soundEnabled ? "1" : "0"
        });
      }
    } catch (error) {
      setStatus(error.message || "Message vocal non transmis.");
    } finally {
      if (activeDuplex === current.duplex) activeDuplex = null;
      busy = false;
      send.disabled = false;
      newChat.disabled = false;
      input.disabled = false;
      mic.disabled = false;
    }
  }

  linkForm.addEventListener("submit", async event => {
    event.preventDefault();
    if (linkPending) return;
    linkCommand = "";
    linkCopy.disabled = true;
    const platform = $("identity-platform").value;
    const accountId = $("identity-id").value.trim();
    if (!["discord", "twitch"].includes(platform) || !/^[1-9][0-9]{0,24}$/.test(accountId)) {
      linkResult.textContent = "Indique un identifiant numérique valide.";
      return;
    }
    if (!token) {
      authorizeAgain();
      return;
    }
    linkPending = true;
    const submit = linkForm.querySelector('button[type="submit"]');
    submit.disabled = true;
    linkResult.textContent = "Création du code de liaison…";
    try {
      const result = await makeRequest("/api/link",
        JSON.stringify({platform, account_id:accountId}),
        {"Content-Type":"application/json"});
      if (typeof result.code !== "string" || !result.code.startsWith("v1.")) {
        throw new Error("Réponse de liaison inattendue.");
      }
      linkCommand = "!jade-memoire confirmer " + result.code;
      linkResult.textContent = linkCommand + "\nÀ envoyer depuis ce même compte " + (platform === "discord" ? "Discord" : "Twitch") + " dans les 5 minutes. Une fois confirmée, l'association n'expire pas.";
      linkCopy.disabled = false;
    } catch (error) {
      linkResult.textContent = error.message || "Liaison indisponible.";
    } finally {
      linkPending = false;
      submit.disabled = false;
    }
  });
  linkCopy.addEventListener("click", async () => {
    if (!linkCommand) return;
    try {
      await navigator.clipboard.writeText(linkCommand);
      linkResult.textContent = "Commande copiée. À envoyer depuis le compte Discord ou Twitch à associer avant l'expiration du code (5 minutes). La liaison restera active.";
    } catch (_) {
      linkResult.textContent = linkCommand + "\nCopie manuellement la commande.";
    }
  });

  const deploymentPanel = $("deployment-panel");
  const deploymentLoad = $("deployment-load"), deploymentRun = $("deployment-run");
  const deploymentRestart = $("deployment-restart"), deploymentBranch = $("deployment-branch");
  const deploymentState = $("deployment-state");
  let deploymentPending = false;

  async function deploymentRequest(operation, extras = {}) {
    return makeRequest("/api/deployment",
      JSON.stringify(Object.assign({operation}, extras)),
      {"Content-Type":"application/json"});
  }

  async function refreshDeployment() {
    if (deploymentPending || !token) return;
    deploymentPending = true;
    deploymentLoad.disabled = true;
    deploymentState.textContent = "Interrogation du superviseur local…";
    try {
      const [current, response] = await Promise.all([
        deploymentRequest("status"), deploymentRequest("branches")
      ]);
      const branchNames = Array.isArray(response.branches) ? response.branches : [];
      const former = deploymentBranch.value;
      deploymentBranch.replaceChildren();
      for (const name of branchNames) {
        if (typeof name !== "string") continue;
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        deploymentBranch.appendChild(option);
      }
      if (branchNames.includes(former)) deploymentBranch.value = former;
      deploymentBranch.disabled = !branchNames.length;
      deploymentRun.disabled = !branchNames.length;
      deploymentState.textContent =
        "Version active : " + (current.sha || "non connue") +
        " ; statut : " + (current.phase || "inconnu") +
        " ; processus : " + (current.running ? "en marche" : "arrêté") +
        (current.error ? " ; incident : " + current.error : "");
    } catch (error) {
      deploymentState.textContent = error.message || "Superviseur indisponible.";
      deploymentBranch.disabled = true;
      deploymentRun.disabled = true;
    } finally {
      deploymentPending = false;
      deploymentLoad.disabled = false;
    }
  }

  async function submitDeployment(operation) {
    if (deploymentPending || !token) return;
    const branch = deploymentBranch.value;
    if (operation === "deploy" && (!branch || deploymentBranch.disabled)) return;
    const question = operation === "deploy"
      ? "Redéployer la branche " + branch + " et redémarrer Jade ?"
      : "Redémarrer Jade sans mettre à jour le code ?";
    if (!window.confirm(question)) return;
    deploymentPending = true;
    deploymentRun.disabled = deploymentRestart.disabled = true;
    deploymentState.textContent = "Demande de redémarrage envoyée…";
    try {
      await deploymentRequest(operation,
        operation === "deploy" ? {branch, confirm:true} : {confirm:true});
      deploymentState.textContent =
        "Redémarrage engagé. La connexion peut être interrompue ; actualise ici après le retour de Jade.";
    } catch (error) {
      deploymentState.textContent = error.message || "Redémarrage non confirmé.";
    } finally {
      deploymentPending = false;
      deploymentRestart.disabled = false;
      deploymentRun.disabled = deploymentBranch.disabled;
    }
  }

  deploymentPanel.addEventListener("toggle", () => {
    if (deploymentPanel.open) refreshDeployment();
  });
  deploymentLoad.addEventListener("click", refreshDeployment);
  deploymentRun.addEventListener("click", () => submitDeployment("deploy"));
  deploymentRestart.addEventListener("click", () => submitDeployment("restart"));

  const billingPanel = $("billing-panel"), billingRefresh = $("billing-refresh");
  const billingStatus = $("billing-status"), billingToday = $("billing-today"), billingMonth = $("billing-month");
  let billingPending = false;
  function formatCosts(costs) {
    if (costs === null || costs === undefined) return "—";
    const entries = Object.entries(costs || {});
    if (!entries.length) return "0 (aucune dépense déclarée)";
    return entries.map(([currency, value]) => `${value} ${currency.toUpperCase()}`).join(" · ");
  }
  async function loadBilling(refresh = false) {
    if (billingPending || !token) return;
    billingPending = true;
    billingRefresh.disabled = true;
    billingStatus.textContent = "Chargement des dépenses…";
    try {
      const result = await makeRequest("/api/billing", JSON.stringify({refresh}), {"Content-Type":"application/json"});
      if (result.status === "ok" || result.status === "stale") {
        billingToday.textContent = formatCosts(result.today);
        billingMonth.textContent = formatCosts(result.month);
        const checked = new Date(result.checked_at).toLocaleString("fr-FR");
        billingStatus.textContent = result.status === "stale"
          ? `Dernière actualisation : ${checked}. Actualisation indisponible.`
          : `Dernière actualisation : ${checked}. Les dépenses peuvent être reportées par OpenAI avec un délai.`;
      } else {
        billingToday.textContent = billingMonth.textContent = "—";
        billingStatus.textContent = result.status === "not_configured"
          ? "Suivi non configuré : une clé administrateur OpenAI est nécessaire sur le PC de Jade."
          : result.status === "access_denied"
            ? "Accès refusé : vérifie la clé administrateur de l’organisation OpenAI."
            : "Dépenses momentanément indisponibles. Réessaie plus tard.";
      }
    } catch (error) {
      billingToday.textContent = billingMonth.textContent = "—";
      billingStatus.textContent = error.message || "Dépenses momentanément indisponibles.";
    } finally {
      billingPending = false;
      billingRefresh.disabled = false;
    }
  }
  billingPanel.addEventListener("toggle", () => { if (billingPanel.open) loadBilling(); });
  billingRefresh.addEventListener("click", () => loadBilling(true));
  setInterval(() => {
    if (billingPanel.open && !document.hidden && token) loadBilling();
  }, 300000);

  authForm.addEventListener("submit", event => {
    event.preventDefault();
    const value = authInput.value;
    if (value.length < 32 || value.length > 256) return;
    token = value;
    authInput.value = "";
    modal.classList.add("hidden");
    setStatus("Jeton saisi. Tu peux parler ou écrire à Jade.");
    input.focus();
  });
  form.addEventListener("submit", submitText);
  input.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  mic.addEventListener("click", () => {
    if (recording) stopRecording();
    else if (activeDuplex && busy) {
      activeDuplex.cancel();
      activeDuplex = null;
      stopPlayback();
      setStatus("Réponse vocale interrompue.");
    } else if (!starting && !busy) startRecording();
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      cancelRecording();
      abortMobileStream();
      if (activeDuplex) { activeDuplex.cancel(); activeDuplex = null; }
      stopPlayback();
    }
  });
  window.addEventListener("pagehide", () => {
    cancelRecording();
    abortMobileStream();
    stopPlayback();
  });
  soundToggle.addEventListener("click", () => {
    soundEnabled = !soundEnabled;
    soundToggle.textContent = soundEnabled ? "Voix activée" : "Voix coupée";
    soundToggle.setAttribute("aria-pressed", String(soundEnabled));
    if (!soundEnabled) stopPlayback();
  });
  newChat.addEventListener("click", () => {
    if (busy || recording || starting) return;
    thread = newThread();
    stopPlayback();
    avatar().resetIntent();
    log.replaceChildren();
    const intro = document.createElement("div");
    intro.className = "welcome";
    intro.textContent = "Un nouveau fil commence. Jade est prête.";
    log.appendChild(intro);
    setStatus("Nouveau fil.");
  });
  $("fullscreen").addEventListener("click", () => {
    if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
    else document.documentElement.requestFullscreen?.().catch(() => {});
  });
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
})();
