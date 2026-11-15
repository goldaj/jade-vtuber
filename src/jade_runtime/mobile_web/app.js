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
  const newChat = $("new-chat"), mood = $("mood-line");
  const avatar = () => window.JadeAvatar || {setMouth() {}, setIntent() {}};
  let token = "";
  let busy = false;
  let recording = null;
  let soundEnabled = true;
  let audioContext = null;
  let playing = null;
  let playFrame = null;
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
    mic.disabled = working && !recording;
  }

  function authorizeAgain() {
    token = "";
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
  }

  async function makeRequest(path, body, extraHeaders) {
    const headers = Object.assign({"Authorization":"Bearer " + token}, extraHeaders);
    const response = await fetch(path, {
      method: "POST", mode: "same-origin", credentials: "omit",
      cache: "no-store", headers, body
    });
    if (response.status === 401 || response.status === 403) {
      authorizeAgain();
      throw new Error("Accès refusé ou session privée expirée.");
    }
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      const messages = {
        429: "Jade est occupée. Réessaie dans quelques instants.",
        504: "La réponse a pris trop de temps."
      };
      throw new Error(messages[response.status] || result.error || "Erreur de communication avec Jade.");
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
    }
    avatar().setMouth(0);
  }

  async function playWav(base64Audio, intent) {
    stopPlayback();
    if (!base64Audio || !soundEnabled) return;
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
      avatar().setIntent(intent);
      playing = src;
      src.onended = () => {
        if (playing === src) {
          playing = null;
          if (playFrame) cancelAnimationFrame(playFrame);
          playFrame = null;
          avatar().setMouth(0);
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
      mood.textContent = "Jade te répond…";
      animateMouth();
    } catch (_) {
      setStatus("Réponse écrite reçue, mais la lecture audio a échoué.");
      avatar().setMouth(0);
    }
  }

  async function present(result) {
    if (result.transcript) addBubble(result.transcript, "me");
    addBubble(String(result.reply || "…"), "jade");
    avatar().setIntent(result.intent || "neutral");
    if (result.audio_wav_b64 && soundEnabled) {
      await playWav(result.audio_wav_b64, result.intent || "neutral");
    } else if (result.audio_unavailable && soundEnabled) {
      setStatus("La réponse est là, mais la synthèse vocale est indisponible.");
      return;
    }
    mood.textContent = "Toujours là, papa.";
    setStatus("Prête.");
  }

  async function submitText(event) {
    event.preventDefault();
    if (busy || recording) return;
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
      const result = await makeRequest("/api/chat",
        JSON.stringify({text, session:thread, speak:soundEnabled}),
        {"Content-Type":"application/json"});
      await present(result);
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
    if (busy || recording) return;
    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus("Microphone indisponible : ouvrir l'application en HTTPS via Tailscale.");
      return;
    }
    stopPlayback();
    let stream, context;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {echoCancellation:true, noiseSuppression:true, autoGainControl:true},
        video: false
      });
      const Ctx = window.AudioContext || window.webkitAudioContext;
      context = new Ctx();
      await context.resume();
      const source = context.createMediaStreamSource(stream);
      const processor = context.createScriptProcessor(4096, 1, 1);
      const silent = context.createGain();
      silent.gain.value = 0;
      const chunks = [];
      let frames = 0;
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
      };
      source.connect(processor);
      processor.connect(silent);
      silent.connect(context.destination);
      recording = {stream, context, source, processor, silent, chunks,
                   get frames() {return frames;}, started:Date.now()};
      mic.classList.add("recording");
      mic.setAttribute("aria-pressed", "true");
      mic.setAttribute("aria-label", "Arrêter et envoyer le message vocal");
      setStatus("J'enregistre ta voix… Touche le micro pour envoyer.");
      // Avoid leaving the microphone open after 20 seconds.
      recording.timer = setTimeout(stopRecording, 20000);
    } catch (_) {
      if (stream) stream.getTracks().forEach(track => track.stop());
      if (context) await context.close().catch(() => {});
      setStatus("Accès au micro refusé ou indisponible.");
    }
  }

  async function stopRecording() {
    const current = recording;
    if (!current) return;
    recording = null;
    // Unlock the playback context while the stop-button gesture is active.
    // Chrome Android may reject a first play() after an awaited network turn.
    if (soundEnabled) ensureAudioContext().catch(() => {});
    clearTimeout(current.timer);
    mic.classList.remove("recording");
    mic.setAttribute("aria-pressed", "false");
    mic.setAttribute("aria-label", "Démarrer l'enregistrement vocal");
    current.processor.onaudioprocess = null;
    current.source.disconnect();
    current.processor.disconnect();
    current.silent.disconnect();
    current.stream.getTracks().forEach(track => track.stop());
    await current.context.close().catch(() => {});
    if (busy) return;
    if (Date.now() - current.started < 250 || current.frames < 4000) {
      setStatus("Enregistrement trop court.");
      return;
    }
    busy = true;
    setStatus("Je transmets ta voix à Jade…", true);
    try {
      const wav = buildWav(current.chunks, current.context.sampleRate, current.frames);
      const result = await makeRequest("/api/voice", wav, {
        "Content-Type":"audio/wav",
        "X-Jade-Session": thread
      });
      await present(result);
    } catch (error) {
      setStatus(error.message || "Message vocal non transmis.");
    } finally {
      busy = false;
      send.disabled = false;
      newChat.disabled = false;
      input.disabled = false;
      mic.disabled = false;
    }
  }

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
    else startRecording();
  });
  soundToggle.addEventListener("click", () => {
    soundEnabled = !soundEnabled;
    soundToggle.textContent = soundEnabled ? "Voix activée" : "Voix coupée";
    soundToggle.setAttribute("aria-pressed", String(soundEnabled));
    if (!soundEnabled) stopPlayback();
  });
  newChat.addEventListener("click", () => {
    if (busy || recording) return;
    thread = newThread();
    stopPlayback();
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
