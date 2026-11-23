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
  const authFeedback = $("auth-feedback"), authSubmit = authForm.querySelector('button[type="submit"]');
  let authPending = false;
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
  const shell = document.querySelector(".shell");
  const navItems = Array.from(document.querySelectorAll(".app-nav-item"));
  function showView(view) {
    if (!["home", "chat", "reminders", "profile"].includes(view)) return;
    shell.dataset.view = view;
    // One microphone control, reparented between Accueil and Chat.
    if (view === "home") document.querySelector?.(".room-bottom")?.appendChild?.(mic);
    else if (mic.parentElement !== form && typeof form.insertBefore === "function")
      form.insertBefore(mic, input);
    navItems.forEach(button => {
      const active = button.dataset.viewTarget === view;
      button.classList.toggle("is-active", active);
      if (active) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
    if (view === "reminders" && token) loadReminders();
    if (view === "profile" && token) refreshNotificationChoice();
  }
  navItems.forEach(button => button.addEventListener("click", () =>
    showView(button.dataset.viewTarget)));

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
    authFeedback.textContent = "";
    modal.classList.remove("hidden");
    connection.classList.remove("online");
    connection.textContent = "Hors connexion";
    setStatus("Accès expiré : ressaisis ton jeton.");
    window.JadeLogin?.show();
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
      if (!item || !/^\/api\/documents\/[a-f0-9]{32}$/.test(item.url)) continue;
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
    showView("chat");
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
  const deploymentLoad = $("deployment-load");
  const deploymentRun = $("deployment-run");
  const deploymentRestart = $("deployment-restart");
  const deploymentState = $("deployment-state"), deploymentVersion = $("deployment-version");
  const deploymentConsole = $("deployment-console"), deploymentFilter = $("deployment-filter");
  const deploymentPause = $("deployment-pause");
  let deploymentPending = false, deploymentTimer = null, deploymentRaw = "", deploymentPaused = false;

  async function controlRequest(path, operation = "GET") {
    const response = await fetch("/control/api/" + path, {
      method: operation, mode: "same-origin", cache: "no-store", credentials: "omit",
      headers: {"Authorization": "Bearer " + token,
                ...(operation === "POST" ? {"Content-Type": "application/json"} : {})},
      ...(operation === "POST" ? {body: JSON.stringify({confirm: true})} : {})
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || "Contrôleur indisponible (HTTP " + response.status + ")");
    return result;
  }

  function renderDeploymentLogs() {
    const lines = deploymentRaw.split("\n");
    const level = deploymentFilter.value;
    const filtered = level === "all" ? lines
      : lines.filter(line => level === "ERROR"
        ? /\b(ERROR|CRITICAL|Traceback|Exception)\b/i.test(line)
        : /\b(WARNING|WARN|ERROR|CRITICAL|Traceback|Exception)\b/i.test(line));
    deploymentConsole.textContent = filtered.join("\n") || "Aucun log pour ce filtre.";
    if (!deploymentPaused) deploymentConsole.scrollTop = deploymentConsole.scrollHeight;
  }

  async function refreshDeployment() {
    if (deploymentPending || !token || !deploymentPanel.open || document.hidden) return;
    deploymentPending = true;
    try {
      const [current, journal] = await Promise.all([
        controlRequest("status"), deploymentPaused ? Promise.resolve(null) : controlRequest("logs")
      ]);
      deploymentState.textContent = current.pycharm_run
        ? "PyCharm Run : connecté · Jade : " + (current.running ? "en marche" : "arrêtée") +
          " · Phase : " + (current.phase || "inconnue") +
          (current.error ? " · Incident : " + current.error : "")
        : "PyCharm Run indisponible ; le contrôleur Windows répond encore.";
      deploymentVersion.textContent = "Branche : " + (current.branch || "inconnue") +
        " · commit : " + (current.sha || "inconnu");
      const ready = current.pycharm_run && current.phase === "idle";
      deploymentRun.disabled = !ready || current.branch !== "develop";
      deploymentRestart.disabled = !ready;
      if (journal && typeof journal.text === "string") {
        deploymentRaw = journal.text;
        renderDeploymentLogs();
      }
    } catch (error) {
      deploymentState.textContent = error.message || "Contrôle indisponible : vérifier Tailscale et le service Windows.";
      deploymentRun.disabled = deploymentRestart.disabled = true;
    } finally {
      deploymentPending = false;
    }
  }

  async function submitDeployment(operation) {
    if (deploymentPending || !token) return;
    if (!window.confirm(operation === "update"
      ? "Mettre à jour develop et redémarrer la session Jade de PyCharm ?"
      : "Redémarrer Jade dans PyCharm sans mise à jour du code ?")) return;
    deploymentPending = true;
    deploymentRun.disabled = deploymentRestart.disabled = true;
    deploymentState.textContent = "Transmission au contrôleur Windows…";
    try {
      await controlRequest(operation, "POST");
      deploymentState.textContent = "Commande acceptée. Suivi du redémarrage en cours.";
    } catch (error) {
      deploymentState.textContent = error.message || "Commande refusée.";
    } finally {
      deploymentPending = false;
      refreshDeployment();
    }
  }

  deploymentPanel.addEventListener("toggle", () => {
    if (deploymentTimer) { clearInterval(deploymentTimer); deploymentTimer = null; }
    if (deploymentPanel.open) {
      refreshDeployment();
      deploymentTimer = setInterval(refreshDeployment, 2500);
    }
  });
  deploymentLoad.addEventListener("click", refreshDeployment);
  deploymentRun.addEventListener("click", () => submitDeployment("update"));
  deploymentRestart.addEventListener("click", () => submitDeployment("restart"));
  deploymentFilter.addEventListener("change", renderDeploymentLogs);
  deploymentPause.addEventListener("click", () => {
    deploymentPaused = !deploymentPaused;
    deploymentPause.textContent = deploymentPaused ? "Reprendre" : "Pause";
    deploymentPause.setAttribute("aria-pressed", String(deploymentPaused));
    if (!deploymentPaused) refreshDeployment();
  });

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

  // DEV-036: reminders live on the PC. The phone never polls while closed.
  // Its service worker is only awakened by the operating system's Push API.
  const remindersList = $("reminders-list");
  const remindersStatus = $("reminder-status");
  const notificationStatus = $("notification-status");
  const reminderForm = $("reminder-form");
  const reminderTitle = $("reminder-title");
  const reminderDate = $("reminder-date");
  const reminderHeaders = {"Content-Type":"application/json"};
  const reminderRequest = (action, id = null, title = null, due_at = null) =>
    makeRequest("/api/reminders", JSON.stringify({action, id, title, due_at}), reminderHeaders);

  function formatReminderDate(seconds) {
    return new Date(Number(seconds) * 1000).toLocaleString("fr-FR", {
      dateStyle:"medium", timeStyle:"short"
    });
  }
  function renderReminders(items) {
    remindersList.replaceChildren();
    if (!items.length) {
      const empty = document.createElement("li");
      empty.textContent = "Aucun rappel enregistré.";
      remindersList.appendChild(empty);
      return;
    }
    for (const reminder of items) {
      const line = document.createElement("li");
      line.id = "reminder-item-" + reminder.id;
      line.tabIndex = -1;
      const info = document.createElement("span");
      const states = {pending:"programmé", retry:"en attente d'envoi",
        sending:"envoi en cours", sent:"envoyé (en attente de ton OK)"};
      info.textContent = reminder.title + " · " + formatReminderDate(reminder.due_at)
        + " · " + (states[reminder.state] || reminder.state)
        + " · " + (reminder.destination === "discord" ? "Discord" : "mobile");
      line.appendChild(info);
      if (reminder.state === "sent") {
        const acknowledge = document.createElement("button");
        acknowledge.type = "button";
        acknowledge.textContent = "OK";
        acknowledge.setAttribute("aria-label", "Confirmer le rappel " + reminder.title);
        acknowledge.addEventListener("click", async () => {
          acknowledge.disabled = true;
          try {
            await reminderRequest("ack", reminder.id);
            await loadReminders();
            remindersStatus.textContent = "Rappel confirmé.";
          } catch (error) {
            remindersStatus.textContent = error.message;
            acknowledge.disabled = false;
          }
        });
        line.appendChild(acknowledge);
      } else {
        const defer = document.createElement("button");
        defer.type = "button";
        defer.textContent = "Reporter 10 min";
        defer.addEventListener("click", async () => {
          try {
            const when = new Date(Date.now() + 10 * 60 * 1000).toISOString();
            await reminderRequest("update", reminder.id, null, when);
            remindersStatus.textContent = "Rappel reporté.";
            await loadReminders();
          } catch (error) { remindersStatus.textContent = error.message; }
        });
        line.appendChild(defer);
      }
      if (reminder.state !== "sent") {
        const cancel = document.createElement("button");
        cancel.type = "button";
        cancel.textContent = "Annuler";
        cancel.addEventListener("click", async () => {
          try {
            await reminderRequest("cancel", reminder.id);
            remindersStatus.textContent = "Rappel annulé.";
            await loadReminders();
          } catch (error) { remindersStatus.textContent = error.message; }
        });
        line.appendChild(cancel);
      }
      remindersList.appendChild(line);
    }
  }
  let remindersLoadVersion = 0;
  async function loadReminders() {
    if (!token) return;
    const version = ++remindersLoadVersion;
    try {
      const result = await reminderRequest("list");
      if (version !== remindersLoadVersion) return;
      renderReminders(result.items || []);
      remindersStatus.textContent = "";
    } catch (error) {
      if (version === remindersLoadVersion)
        remindersStatus.textContent = "Rappels indisponibles : " + error.message;
    }
  }
  // Refresh only while the reminders tab is actually open. No background PWA polling.
  setInterval(() => {
    if (token && !document.hidden && shell.dataset.view === "reminders")
      loadReminders();
  }, 30000);
  reminderForm.addEventListener("submit", async event => {
    event.preventDefault();
    if (!token) { authorizeAgain(); return; }
    const title = reminderTitle.value.trim();
    const date = new Date(reminderDate.value);
    if (!title || Number.isNaN(date.getTime())) {
      remindersStatus.textContent = "Titre et date valides requis.";
      return;
    }
    try {
      await reminderRequest("create", null, title, date.toISOString());
      reminderForm.reset();
      $("reminder-create-panel").open = false;
      remindersStatus.textContent = "Rappel enregistré sur le PC.";
      await loadReminders();
    } catch (error) { remindersStatus.textContent = error.message; }
  });
  $("refresh-reminders").addEventListener("click", loadReminders);

  const decodeVapidKey = value => {
    const base64 = value.replace(/-/g, "+").replace(/_/g, "/");
    const binary = atob(base64.padEnd(Math.ceil(base64.length / 4) * 4, "="));
    return Uint8Array.from(binary, char => char.charCodeAt(0));
  };
  async function registrationForPush() {
    if (!window.isSecureContext || !("serviceWorker" in navigator) ||
        !("PushManager" in window) || !("Notification" in window)) {
      throw new Error("Ce navigateur ne prend pas en charge le push pour cette PWA.");
    }
    return navigator.serviceWorker.ready;
  }
  const notificationOn = $("notifications-on"), notificationOff = $("notifications-off");
  let confirmedNotificationChoice = "";
  let notificationBusy = false;
  function showNotificationChoice(value) {
    notificationOn.checked = value === "on";
    notificationOff.checked = value === "off";
  }
  function lockNotificationChoice(value) {
    notificationOn.disabled = value;
    notificationOff.disabled = value;
  }
  // Refresh from browser state. Never prompt for permission while rendering the page.
  async function refreshNotificationChoice() {
    if (!token || notificationBusy) return;
    try {
      const registration = await registrationForPush();
      const subscription = await registration.pushManager.getSubscription();
      confirmedNotificationChoice = subscription && Notification.permission === "granted" ? "on" : "off";
      showNotificationChoice(confirmedNotificationChoice);
      lockNotificationChoice(false);
      notificationStatus.textContent = confirmedNotificationChoice === "on"
        ? "Notifications activées sur cet appareil." : "Notifications désactivées sur cet appareil.";
    } catch (error) {
      confirmedNotificationChoice = "";
      showNotificationChoice("");
      lockNotificationChoice(true);
      notificationStatus.textContent = "Notifications indisponibles : " + error.message;
    }
  }
  async function changeNotificationChoice(enable) {
    if (notificationBusy) return;
    if (!token) { showNotificationChoice(confirmedNotificationChoice); authorizeAgain(); return; }
    notificationBusy = true;
    lockNotificationChoice(true);
    try {
      const registration = await registrationForPush();
      if (enable) {
        const config = await makeRequest("/api/push", JSON.stringify({action:"config"}), reminderHeaders);
        if (!config.enabled) throw new Error("Push non configuré sur le PC Jade.");
        if (await Notification.requestPermission() !== "granted")
          throw new Error("Permission de notifications refusée.");
        let subscription = await registration.pushManager.getSubscription();
        if (!subscription) subscription = await registration.pushManager.subscribe({
          userVisibleOnly:true, applicationServerKey:decodeVapidKey(config.vapid_public_key)
        });
        await makeRequest("/api/push", JSON.stringify({
          action:"subscribe", subscription:subscription.toJSON()
        }), reminderHeaders);
      } else {
        const subscription = await registration.pushManager.getSubscription();
        if (subscription) {
          await makeRequest("/api/push", JSON.stringify({
            action:"unsubscribe", endpoint:subscription.endpoint
          }), reminderHeaders);
          if (!await subscription.unsubscribe())
            throw new Error("Le navigateur n'a pas confirmé la désinscription.");
        }
      }
      confirmedNotificationChoice = enable ? "on" : "off";
      showNotificationChoice(confirmedNotificationChoice);
      notificationStatus.textContent = enable
        ? "Notifications activées sur cet appareil." : "Notifications désactivées sur cet appareil.";
    } catch (error) {
      showNotificationChoice(confirmedNotificationChoice);
      notificationStatus.textContent = (enable ? "Activation impossible : " : "Désactivation incomplète : ") + error.message;
    } finally {
      notificationBusy = false;
      lockNotificationChoice(false);
    }
  }
  notificationOn.addEventListener("change", () => {
    if (notificationOn.checked) changeNotificationChoice(true);
  });
  notificationOff.addEventListener("change", () => {
    if (notificationOff.checked) changeNotificationChoice(false);
  });

  async function showReminder(reminderId) {
    if (!/^[0-9a-f]{24}$/.test(reminderId)) return;
    showView("reminders");
    if (!token) return;
    try {
      const result = await makeRequest("/api/reminders", JSON.stringify({
        action:"get", id:reminderId
      }), reminderHeaders);
      const reminder = result.reminder;
      remindersStatus.textContent = "Rappel Jade : " + reminder.title + " · "
        + formatReminderDate(reminder.due_at) + ".";
      await loadReminders();
      const row = $("reminder-item-" + reminderId);
      if (row) {
        row.classList.add("reminder-highlight");
        row.scrollIntoView?.({block:"nearest"});
      }
      remindersStatus.textContent = "Rappel Jade : " + reminder.title + " · "
        + formatReminderDate(reminder.due_at) + ".";
    } catch (error) {
      remindersStatus.textContent = "Rappel inaccessible : " + error.message;
    }
  }
  function openReminderFromHash() {
    const match = /^#reminder-([0-9a-f]{24})$/.exec(window.location.hash);
    if (match) showReminder(match[1]);
  }
  window.addEventListener("hashchange", openReminderFromHash);
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.addEventListener("message", event => {
      if (event.data && event.data.type === "jade-open-reminder" &&
          typeof event.data.id === "string" && /^[0-9a-f]{24}$/.test(event.data.id)) {
        const target = "#reminder-" + event.data.id;
        if (window.location.hash === target) showReminder(event.data.id);
        else window.location.hash = target;
      }
    });
  }
  openReminderFromHash();

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
    } else if (token && shell.dataset.view === "reminders") {
      loadReminders();
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
    setStatus("Nouveau fil.");
  });
  const fullscreenButton = $("fullscreen");
  const roomPlane = document.querySelector(".room-plane");
  let nativeRoomFullscreen = false;
  function setRoomFullscreen(active) {
    // Freeze the 4:3 background width before its enclosing viewport expands.
    if (active && roomPlane) {
      const width = roomPlane.getBoundingClientRect().width;
      if (width > 0) shell.style.setProperty("--room-immersive-width", width + "px");
    }
    shell.classList.toggle("is-room-only", active);
    if (!active) shell.style.removeProperty("--room-immersive-width");
    fullscreenButton.textContent = active ? "⤢" : "⛶";
    const description = active ? "Quitter le plein écran" : "Afficher uniquement Jade en plein écran";
    fullscreenButton.setAttribute("aria-label", description);
    fullscreenButton.setAttribute("title", description);
    fullscreenButton.setAttribute("aria-pressed", String(active));
    window.JadeAvatar?.resize?.();
  }
  fullscreenButton.addEventListener("click", async () => {
    if (shell.classList.contains("is-room-only")) {
      setRoomFullscreen(false);
      if (document.fullscreenElement) {
        try { await document.exitFullscreen?.(); } catch (_) { /* CSS view already closed */ }
      }
      return;
    }
    setRoomFullscreen(true);
    if (shell.requestFullscreen) {
      try { await shell.requestFullscreen(); } catch (_) { /* CSS fullscreen stays available */ }
    }
  });
  document.addEventListener("fullscreenchange", () => {
    if (document.fullscreenElement === shell) nativeRoomFullscreen = true;
    else if (nativeRoomFullscreen) {
      nativeRoomFullscreen = false;
      setRoomFullscreen(false);
    }
  });
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
  // Chat is initialized independently of the optional Live2D renderer.
  window.JadeMobileApp = {
    login(value) {
      token = value;
      authInput.value = "";
      authFeedback.textContent = "";
      modal.classList.add("hidden");
      connection.textContent = "Connectée à Jade";
      connection.classList.add("online");
      setStatus("Connexion vérifiée. Tu peux parler ou écrire à Jade.");
      // Do not display the Android keyboard on the room-first landing page.
      openReminderFromHash();
      if (shell.dataset.view === "reminders") {
        loadReminders();
      }
      if (shell.dataset.view === "profile") refreshNotificationChoice();
    }
  };
})();
