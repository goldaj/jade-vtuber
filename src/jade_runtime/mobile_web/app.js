/* Jade owner-only phone client. Only non-sensitive interface preferences are
 * persisted by JadePreferences; tokens, conversations and media stay in memory.
 * No analytics, third-party servers, remote libraries or alternative AI engines.
 * Classic voice uses Jade's existing STT; optional Live uses its own WebRTC
 * client. Only one of those paths may own capture and audible output.
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
  const liveModeToggle = $("live-mode-toggle"), liveModeStatus = $("live-mode-status");
  const liveModeRetry = $("live-mode-retry");
  const liveIndicator = $("live-indicator");
  const preferences = window.JadePreferences;
  let liveClient = null, liveState = null, liveMotionPending = false, liveSpeaking = false;
  let liveLoadMessage = "", liveRetrying = false;
  let liveAuthentication = 0;
  const liveTranscripts = new Map();
  const linkForm = $("identity-link-form"), linkResult = $("identity-result");
  const linkCopy = $("identity-copy");
  let linkCommand = "";
  let linkPending = false;
  const avatar = () => window.JadeAvatar || {setMouth() {}, setIntent() {}, setSpeaking() {}, resetIntent() {}};
  let token = "";
  let busy = false;
  let recording = null;
  let starting = null;
  let micPress = null;
  let voicePending = false;
  let conversationGeneration = 0;
  let modelChanging = false;
  let soundEnabled = preferences?.get("soundEnabled", true) ?? true;
  soundToggle.checked = soundEnabled;
  let audioContext = null;
  let playFrame = null;
  let playbackGeneration = 0;
  let replyPlayback = null;
  const REPLY_FACE_LEAD_MS = 200;
  let streamController = null;
  let activeDuplex = null;
  const audioSources = new Set();
  let playbackAnalyser = null;
  let nextAudioTime = 0;
  let thread = newThread();
  const shell = document.querySelector(".shell");
  const navItems = Array.from(document.querySelectorAll(".app-nav-item"));
  // Move the existing control, preserving its recording and disabled states.
  function syncMicPlacement() {
    if (shell.dataset.view === "home" || shell.classList.contains("is-room-only")) {
      const dock = document.querySelector?.(".room-bottom");
      if (dock && mic.parentElement !== dock) dock.appendChild?.(mic);
    } else if (mic.parentElement !== form && typeof form.insertBefore === "function") {
      form.insertBefore(mic, input);
    }
  }
  function showView(view) {
    if (!["home", "chat", "reminders", "profile"].includes(view)) return;
    if (view !== shell.dataset.view) finishMicPress(false);
    shell.dataset.view = view;
    syncMicPlacement();
    window.JadeAvatar?.resize?.();
    navItems.forEach(button => {
      const active = button.dataset.viewTarget === view;
      button.classList.toggle("is-active", active);
      if (active) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
    if (view === "reminders" && token) loadReminders();
    if (view === "profile" && token) {
      refreshNotificationChoice();
      liveClient?.refresh();
      if (discordLivePanel?.open) refreshDiscordLive();
    }
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
    working = working || modelChanging;
    status.textContent = message;
    send.disabled = working;
    newChat.disabled = working;
    input.disabled = working;
    mic.disabled = modelChanging || (working && !micPress && !voicePending);
    renderLiveMic();
  }

  function resetLiveAuthentication(reason) {
    // Stop the previous media owner before discarding its reference. Each
    // authentication gets a fresh preference read and its own pending reads.
    cancelConversation(reason);
    liveAuthentication++;
    liveClient = liveState = null;
    liveLoadMessage = "";
    liveRetrying = false;
    if (liveModeToggle) liveModeToggle.disabled = true;
    resetDiscordLivePanel();
  }

  function authorizeAgain() {
    resetLiveAuthentication("auth_lost");
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
    appendAttachments(entry, files);
    return entry;
  }

  function appendAttachments(entry, files) {
    if (!entry) return;
    const attached = entry.jadeAttachmentUrls || (entry.jadeAttachmentUrls = new Set());
    for (const item of Array.isArray(files) ? files.slice(0, 4) : []) {
      if (!item || !/^\/api\/documents\/[a-f0-9]{32}$/.test(item.url)) continue;
      if (attached.has(item.url)) continue;
      attached.add(item.url);
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
  }

  function liveOnAir() {
    return liveState?.capture === "armed" &&
      (["opening", "active"].includes(liveState.session_state) ||
        liveState.media_state === "connecting" ||
        liveState.speech_active === true || liveState.playback_active === true);
  }

  function liveDescription() {
    if (liveLoadMessage) return liveLoadMessage;
    if (!liveState) return "Vérification du mode vocal…";
    if (!liveState.supported) return liveState.availability_message ||
      "Ce navigateur ne permet pas le mode Live.";
    if (liveState.message) return liveState.message;
    if (!liveState.loaded) return "Vérification du mode vocal…";
    if (!liveState.available && !liveState.active) return liveState.availability_message ||
      "Le mode Live est momentanément indisponible.";
    if (liveState.mode !== "live") return "";
    if (liveState.lease_state === "draining") return "Micro coupé. Jade termine sa réponse.";
    if (liveState.capture === "requesting") return "Ouverture du micro…";
    if (liveState.capture === "closed" && liveState.session_state === "closing") return "Micro coupé · Fermeture du Live…";
    if (liveState.capture === "armed") {
      if (liveState.session_state === "opening" || liveState.media_state === "connecting") return "Micro actif · Connexion à Jade…";
      return liveOnAir() ? "Live en cours." : "Micro actif · Jade en veille. Parle quand tu veux.";
    }
    return "";
  }

  function renderLiveMic() {
    const enabled = Boolean(token && liveState?.loaded && liveState.mode === "live");
    const capturing = enabled && liveState.capture !== "closed";
    const onAir = enabled && liveOnAir();
    if (liveIndicator) {
      liveIndicator.hidden = !enabled;
      liveIndicator.classList.toggle("live-on-air", onAir);
      liveIndicator.setAttribute("aria-label", onAir ? "Live en cours" : "Live en veille");
    }
    mic.classList.toggle("live-mode-indicator", enabled);
    mic.classList.toggle("live-on-air", onAir);
    if (!liveState?.loaded) {
      // Until the owner's persisted choice is known, a tap cannot fall through
      // to classic capture while the default Live module is still loading.
      if (token) {
        mic.disabled = true;
        mic.setAttribute("aria-label", "Vérification du mode vocal");
      }
    } else if (!enabled) {
      mic.disabled = modelChanging || (busy && !micPress && !voicePending);
    } else {
      const draining = liveState.lease_state === "draining";
      mic.classList.remove("recording");
      mic.disabled = modelChanging || busy || liveState.changing ||
        (liveState.capture === "closed" && liveState.session_state === "closing" && !draining) ||
        (!liveState.active && (!liveState.available || !soundEnabled));
      mic.setAttribute("aria-pressed", String(capturing));
      mic.setAttribute("aria-label", draining ? "Interrompre la réponse Live" : "Micro Live");
    }
  }

  function renderLiveAvailability() {
    if (liveModeStatus) {
      const description = liveDescription();
      liveModeStatus.textContent = description;
      liveModeStatus.hidden = !description;
    }
    if (liveModeRetry) {
      liveModeRetry.hidden = !(liveLoadMessage || (!liveState?.loaded && liveState?.message) ||
        (liveState?.loaded && !liveState.available && liveState.supported));
      liveModeRetry.disabled = liveRetrying;
      liveModeRetry.textContent = liveRetrying ? "Vérification…" : "Réessayer";
    }
    renderLiveMic();
  }

  function liveModuleFailed() {
    liveLoadMessage = "Le mode Live n’a pas pu charger. Réessaie depuis Config.";
    if (liveModeToggle) liveModeToggle.disabled = true;
    renderLiveAvailability();
  }

  function renderLiveState(value) {
    const wasLive = liveState?.mode === "live";
    const hadPreference = liveState?.loaded;
    const wasActive = liveState?.active;
    const hadSession = liveState?.session_id;
    liveState = value;
    liveLoadMessage = "";
    if (liveModeToggle) {
      liveModeToggle.checked = Boolean(value.loaded && value.mode === "live");
      // Turning OFF remains possible after a kill switch, provider refusal
      // or loss of browser capability. Admission restrictions only gate ON.
      liveModeToggle.disabled = value.changing || !value.loaded ||
        (value.mode !== "live" && !value.available);
    }
    if (value.loaded && value.mode !== "live" && (wasLive || !hadPreference)) {
      resetMicButton();
      mic.disabled = modelChanging || (busy && !micPress && !voicePending);
    }
    renderLiveAvailability();
    if (((wasActive && !value.active) || (hadSession && !value.session_id)) && !busy && !voicePending) {
      liveMotionPending = liveSpeaking = false;
      avatar().setMouth(0);
      avatar().setSpeaking(false);
      avatar().resetIntent();
    }
  }

  function receiveLiveTranscript(event) {
    const sessionId = String(event.session_id || "");
    if (!sessionId) return;
    let session = liveTranscripts.get(sessionId);
    if (!session) {
      session = {entries:new Map(), documents:null, lastJade:null};
      liveTranscripts.set(sessionId, session);
    }
    const segments = Array.isArray(event.segments) ? event.segments : [event];
    const present = new Set();
    for (const segment of segments) {
      const id = String(segment.segment_id || "");
      const text = String(segment.text || "").replace(/\[INTENT\s*:[^\]]*\]/gi, "").trim();
      if (!id || !text || !["user", "assistant"].includes(segment.role)) continue;
      present.add(id);
      let item = session.entries.get(id);
      if (!item) {
        const entry = addBubble(text, segment.role === "assistant" ? "jade" : "me");
        const delivery = document.createElement("small");
        delivery.className = "live-transcript-status";
        entry.appendChild(delivery);
        item = {entry, content:entry.firstElementChild || entry.children[0], delivery, role:segment.role};
        session.entries.set(id, item);
      }
      item.content.textContent = text;
      const labels = {interrupted:"Réponse interrompue", cancelled:"Tour annulé", delivery_unknown:"Lecture non confirmée"};
      item.delivery.textContent = labels[segment.status] || "Transcription Live";
      item.entry.setAttribute("data-live-status", segment.status || "received");
      if (segment.role === "assistant") session.lastJade = item.entry;
      if (segment.attachments) receiveLiveAttachments(session, segment.attachments);
    }
    if (event.replace) {
      for (const [id, item] of session.entries) {
        if (present.has(id)) continue;
        item.entry.remove();
        session.entries.delete(id);
      }
      // Snapshot order can change when a late fragment joins two segments.
      for (const segment of segments) {
        const item = session.entries.get(String(segment.segment_id));
        if (item) log.appendChild(item.entry);
      }
      session.lastJade = [...segments].reverse().map(segment => session.entries.get(String(segment.segment_id)))
        .find(item => item?.role === "assistant")?.entry || null;
    }
    if (event.attachments) receiveLiveAttachments(session, event.attachments);
    if (session.documents) log.appendChild(session.documents);
    log.scrollTop = log.scrollHeight;
  }

  function receiveLiveAttachments(session, files) {
    const valid = (Array.isArray(files) ? files : []).filter(item => item && /^\/api\/documents\/[a-f0-9]{32}$/.test(item.url));
    if (!valid.length) return;
    // An action can finish before Jade's spoken reply. Display its documents
    // immediately without inventing another assistant message or attaching
    // them to the preceding, unrelated transcript segment.
    if (!session.documents) {
      session.documents = document.createElement("article");
      session.documents.className = "bubble jade live-attachments";
      session.documents.setAttribute("aria-label", "Documents de la conversation Live");
    }
    appendAttachments(session.documents, valid);
    log.appendChild(session.documents);
  }

  function initializeLive() {
    if (!window.JadeLive || !token) return;
    try {
      if (!liveClient) {
      const generation = liveAuthentication, authenticatedToken = token;
      const options = {
      getToken:() => authenticatedToken, getThread:() => thread, getSoundEnabled:() => soundEnabled,
      beforeArm:() => cancelConversation("live_arm", {keepLive:true}),
      onState:renderLiveState,
      onTranscript:receiveLiveTranscript,
      onInterruption:(sessionId, status) => {
        const session = liveTranscripts.get(sessionId);
        const item = session && [...session.entries.values()].find(value => value.entry === session.lastJade);
        if (!item) return;
        item.entry.setAttribute("data-live-status", status);
        item.delivery.textContent = status === "interrupted" ? "Réponse interrompue" : "Lecture non confirmée";
      },
      onAttachments:event => {
        let session = liveTranscripts.get(event.session_id);
        if (!session) {
          session = {entries:new Map(), documents:null, lastJade:null};
          liveTranscripts.set(event.session_id, session);
        }
        receiveLiveAttachments(session, event.attachments);
      },
      onIntent:intent => {
        applyAvatarIntent(intent, !liveSpeaking);
        liveMotionPending = !liveSpeaking;
      },
      onPlayback:(level, speaking) => {
        avatar().setMouth(level);
        avatar().setSpeaking(speaking);
        if (speaking && liveMotionPending) { avatar().startReplyMotion?.(0); liveMotionPending = false; }
        liveSpeaking = speaking;
      },
      onAuthFailure:() => { if (token) authorizeAgain(); },
      };
      for (const name of ["beforeArm", "onState", "onTranscript", "onInterruption", "onAttachments", "onIntent", "onPlayback", "onAuthFailure"]) {
        const callback = options[name];
        options[name] = (...args) => {
          if (generation === liveAuthentication) return callback(...args);
        };
      }
      liveClient = window.JadeLive.create(options);
      }
      if (liveClient.state) renderLiveState(liveClient.state);
      if (token) void liveClient.refresh();
    } catch (_) { liveModuleFailed(); }
  }
  window.addEventListener("jade-live-ready", initializeLive);
  liveModeRetry?.addEventListener("click", async () => {
    if (liveRetrying || !token) return;
    const generation = liveAuthentication;
    liveRetrying = true;
    liveLoadMessage = "";
    renderLiveAvailability();
    try {
      if (liveClient) await liveClient.refresh();
      else {
        const ready = await window.JadeLogin?.retryLive?.();
        if (generation === liveAuthentication && !ready) liveModuleFailed();
      }
    } catch (_) { if (generation === liveAuthentication) liveModuleFailed(); }
    finally {
      if (generation === liveAuthentication) { liveRetrying = false; renderLiveAvailability(); }
    }
  });
  liveModeToggle?.addEventListener("change", () => {
    if (!liveClient || !liveState?.loaded || liveState.changing) return;
    const mode = liveModeToggle.checked ? "live" : "classic";
    cancelConversation("mode_change");
    return liveClient.setMode(mode);
  });

  function applyAvatarIntent(intent, deferMotion) {
    return avatar().setIntent(intent || "neutral", {deferMotion});
  }

  function setReplyIntent(intent) {
    const prepared = applyAvatarIntent(intent, soundEnabled);
    replyPlayback = {
      faceReadyAt:prepared && soundEnabled ? performance.now() + REPLY_FACE_LEAD_MS : 0,
      started:false, sealed:false,
    };
  }

  async function makeRequest(path, body, extraHeaders, signal) {
    const headers = Object.assign({"Authorization":"Bearer " + token}, extraHeaders);
    const response = await fetch(path, {
      method: body === undefined ? "GET" : "POST", mode: "same-origin", credentials: "omit",
      cache: "no-store", headers, body, signal
    });
    if (signal?.aborted) return null;
    if (response.status === 401) {
      authorizeAgain();
      throw new Error("Jeton mobile incorrect : ressaisis-le.");
    }
    if (response.status === 403) {
      throw new Error("Accès réservé au propriétaire Tailscale : vérifie ton VPN et ton identité.");
    }
    const result = await response.json().catch(() => ({}));
    if (signal?.aborted) return null;
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

  function primeVoicePlayback() {
    if (!soundEnabled) return;
    try { ensureAudioContext().catch(() => {}); }
    catch (_) { /* A failed output device must not block the user's message. */ }
  }

  function stopMouthPlayback() {
    if (playFrame) cancelAnimationFrame(playFrame);
    playFrame = null;
    playbackAnalyser?.disconnect();
    playbackAnalyser = null;
    avatar().setMouth(0);
  }

  function stopPlayback() {
    playbackGeneration++;
    replyPlayback = null;
    for (const source of audioSources) {
      source.onended = null;
      try { source.stop(); } catch (_) {}
      source.disconnect();
    }
    audioSources.clear();
    nextAudioTime = 0;
    stopMouthPlayback();
    avatar().setSpeaking(false);
    avatar().resetIntent();
  }

  function finishDrainedReply() {
    if (!replyPlayback?.sealed || audioSources.size) return;
    const hadAudio = replyPlayback.started;
    replyPlayback = null;
    nextAudioTime = 0;
    if (hadAudio) avatar().setSpeaking(false);
    avatar().finishReply?.(hadAudio);
  }

  function sealReplyAudio() {
    if (!replyPlayback) return;
    replyPlayback.sealed = true;
    finishDrainedReply();
  }

  function cancelConversation(reason = "conversation_cancelled", {keepLive = false} = {}) {
    const liveStopped = keepLive ? null : liveClient?.stop(typeof reason === "string" ? reason : "pagehide");
    conversationGeneration++;
    clearMicPress();
    cancelRecordingStart();
    cancelRecording();
    streamController?.abort();
    streamController = null;
    activeDuplex?.cancel();
    activeDuplex = null;
    busy = false;
    voicePending = false;
    resetMicButton();
    stopPlayback();
    setStatus(status.textContent);
    return liveStopped;
  }

  function stopForModelChange() {
    modelChanging = true;
    cancelConversation("model_change");
    setStatus("Chargement du modèle…");
    return () => {
      modelChanging = false;
      setStatus(token ? "Prête." : status.textContent);
    };
  }

  function createMobileAudioTiming(transport) {
    const startedAt = performance.now();
    let firstReceivedAt = null, firstScheduledAt = null;
    let gapCount = 0, gapMs = 0;
    return {
      received() {
        if (firstReceivedAt === null) firstReceivedAt = performance.now();
      },
      scheduled(result) {
        if (!result) return;
        if (firstScheduledAt === null) firstScheduledAt = result.scheduledAt;
        if (result.gapMs >= 1) {
          gapCount++;
          gapMs += result.gapMs;
        }
      },
      done() {
        const endedAt = performance.now();
        const ms = value => value === null ? null : Math.round(value - startedAt);
        console.info("jade.mobile.audio", JSON.stringify({
          event: "rec029_mobile_pcm_client", transport,
          first_pcm_received_ms: ms(firstReceivedAt),
          first_play_scheduled_ms: ms(firstScheduledAt),
          stream_finished_ms: ms(endedAt),
          playback_gaps: gapCount,
          playback_gap_ms: Math.round(gapMs),
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
    const generation = playbackGeneration;
    const context = await ensureAudioContext();
    if (generation !== playbackGeneration || !replyPlayback) return null;
    const buffer = context.createBuffer(1, binary.length / 2, rate);
    const samples = buffer.getChannelData(0);
    for (let i = 0; i < samples.length; i++) {
      let value = binary.charCodeAt(i * 2) | (binary.charCodeAt(i * 2 + 1) << 8);
      if (value >= 32768) value -= 65536;
      samples[i] = value / 32768;
    }
    return scheduleAudio(context, buffer);
  }

  function scheduleAudio(context, buffer) {
    const reply = replyPlayback;
    if (!reply || reply.sealed) return null;
    const now = performance.now(), audioNow = context.currentTime;
    const gapMs = reply.started ? Math.max(0, audioNow - nextAudioTime) * 1000 : 0;
    // Keep adjacent fragments contiguous. A depleted queue can resume
    // immediately if audio already ran, without adding another 50 ms gap.
    const start = reply.started ? Math.max(audioNow, nextAudioTime)
      : audioNow + Math.max(.05, (reply.faceReadyAt - now) / 1000);
    const newAnalyser = !playbackAnalyser;
    if (newAnalyser) {
      playbackAnalyser = context.createAnalyser();
      playbackAnalyser.fftSize = 1024;
      playbackAnalyser.connect(context.destination);
    }
    const source = context.createBufferSource();
    source.buffer = buffer;
    source.connect(playbackAnalyser);
    source.onended = () => {
      if (!audioSources.delete(source)) return;
      source.disconnect();
      if (!audioSources.size) stopMouthPlayback();
      finishDrainedReply();
    };
    try {
      source.start(start);
    } catch (error) {
      source.disconnect();
      if (newAnalyser) stopMouthPlayback();
      throw error;
    }
    audioSources.add(source);
    nextAudioTime = start + buffer.duration;
    const delayMs = (start - audioNow) * 1000;
    if (!reply.started) {
      reply.started = true;
      avatar().setSpeaking(true);
      avatar().startReplyMotion?.(delayMs);
    }
    if (newAnalyser) {
      const analyser = playbackAnalyser, data = new Uint8Array(analyser.fftSize);
      const animate = () => {
        if (playbackAnalyser !== analyser) return;
        analyser.getByteTimeDomainData(data);
        let sum = 0;
        for (const value of data) sum += ((value - 128) / 128) ** 2;
        avatar().setMouth(Math.min(1, Math.sqrt(sum / data.length) * 7));
        playFrame = requestAnimationFrame(animate);
      };
      animate();
    }
    return {scheduledAt:now + delayMs, gapMs};
  }

  async function makeStreamingRequest(path, body, extraHeaders) {
    const generation = conversationGeneration;
    const isCurrent = () => generation === conversationGeneration;
    const controller = typeof AbortController === "undefined" ? null : new AbortController();
    streamController = controller;
    // Choose the legacy format before sending anything: retrying afterward
    // could produce a second billable conversation and voice synthesis.
    try {
      if (!controller || typeof ReadableStream === "undefined" || typeof TextDecoder === "undefined") {
        const result = await makeRequest(path, body, extraHeaders, controller?.signal);
        if (isCurrent()) await present(result, generation);
        return;
      }
      const headers = Object.assign({"Authorization":"Bearer " + token, "X-Jade-Stream":"1"}, extraHeaders);
      const response = await fetch(path, {method:"POST", mode:"same-origin", credentials:"omit",
        cache:"no-store", headers, body, signal:controller.signal});
      if (!isCurrent()) return;
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
        else if (event.type === "done") { done = true; audioTiming.done(); sealReplyAudio(); }
        else throw new Error("Réponse audio inattendue.");
      }
      while (true) {
        const part = await reader.read();
        if (!isCurrent()) return;
        pending += decoder.decode(part.value || new Uint8Array(), {stream:!part.done});
        if (pending.length > 10_000_000) throw new Error("Réponse audio trop volumineuse.");
        let newline;
        while ((newline = pending.indexOf("\n")) !== -1) {
          const line = pending.slice(0, newline); pending = pending.slice(newline + 1);
          if (line) await consume(line);
          if (!isCurrent()) return;
        }
        if (part.done) break;
      }
      if (!isCurrent()) return;
      if (pending || !done || !receivedReply) throw new Error("Réponse audio interrompue.");
      setStatus(audioFailed && soundEnabled ? audioUnavailableStatus(audioFailureReason) : "Prête.");
    } finally {
      if (isCurrent()) {
        streamController = null;
        sealReplyAudio();
      }
    }
  }

  async function playWav(base64Audio) {
    if (!base64Audio || !soundEnabled || document.hidden) return true;
    const generation = playbackGeneration;
    try {
      const context = await ensureAudioContext();
      if (generation !== playbackGeneration || !replyPlayback) return true;
      // Limit the size of an untrusted API response.
      if (base64Audio.length > 10_000_000) throw new Error("audio too large");
      const binary = atob(base64Audio);
      const bytes = Uint8Array.from(binary, c => c.charCodeAt(0));
      const decoded = await context.decodeAudioData(bytes.buffer.slice(0));
      if (generation !== playbackGeneration) return true;
      scheduleAudio(context, decoded);
      return true;
    } catch (_) {
      if (generation !== playbackGeneration) return true;
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

  async function present(result, generation) {
    if (result.transcript) addBubble(result.transcript, "me");
    addJadeReply(String(result.reply || "…"), result.attachments);
    setReplyIntent(result.intent);
    if (result.audio_wav_b64 && soundEnabled) {
      const played = await playWav(result.audio_wav_b64);
      if (generation !== conversationGeneration) return;
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
    if (modelChanging || busy || recording || starting) return;
    if (!token) { authorizeAgain(); return; }
    const text = input.value.trim();
    if (!text) return;
    const generation = conversationGeneration;
    const liveStopped = liveClient?.stop("text");
    showView("chat");
    busy = true;
    stopPlayback();
    setStatus("Jade réfléchit…", true);
    // Unlock audio during user gesture, before the asynchronous fetch.
    if (soundEnabled) ensureAudioContext().catch(() => {});
    addBubble(text, "me");
    input.value = "";
    try {
      await liveStopped;
      if (generation !== conversationGeneration) return;
      await makeStreamingRequest("/api/chat",
        JSON.stringify({text, session:thread, speak:soundEnabled}),
        {"Content-Type":"application/json"});
    } catch (error) {
      if (generation === conversationGeneration) setStatus(error.message || "Impossible de joindre Jade.");
    } finally {
      if (generation === conversationGeneration) {
        busy = false;
        setStatus(status.textContent);
        input.focus();
      }
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

  function clearMicPress() {
    const pointerId = micPress?.pointerId;
    micPress = null;
    try {
      if (pointerId !== undefined && mic.hasPointerCapture?.(pointerId))
        mic.releasePointerCapture(pointerId);
    } catch (_) { /* The browser may already have dropped the pointer. */ }
  }

  function finishMicPress(sendUtterance) {
    const press = micPress;
    if (!press) return;
    clearMicPress();
    if (press.interrupt) {
      if (sendUtterance && voicePending) {
        cancelConversation();
        setStatus("Réponse vocale interrompue.");
      }
    } else if (starting) {
      cancelRecordingStart();
      resetMicButton();
      setStatus(sendUtterance ? "Micro relâché avant le début de la prise." : "Prise vocale annulée.");
    } else if (sendUtterance) {
      void stopRecording();
    } else {
      cancelRecording();
    }
  }

  async function startRecording(press) {
    if (modelChanging || document.hidden || micPress || recording || starting || (busy && !voicePending)) return;
    if (!token) { authorizeAgain(); return; }
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!voicePending && (!navigator.mediaDevices?.getUserMedia || !Ctx)) {
      setStatus("Microphone indisponible : ouvrir l'application en HTTPS via Tailscale.");
      return;
    }
    micPress = {...press, interrupt:voicePending};
    if (press.pointerId !== undefined) {
      try { mic.setPointerCapture?.(press.pointerId); }
      catch (_) { /* The window still observes release and cancellation. */ }
    }
    if (voicePending) return;
    stopPlayback();
    const attempt = {}, generation = conversationGeneration;
    starting = attempt;
    setStatus("Ouverture du micro… Garde ton appui.", true);
    let duplex = null;
    try {
      primeVoicePlayback();
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {echoCancellation:true, noiseSuppression:true, autoGainControl:true},
        video: false
      });
      if (starting !== attempt) {
        stream.getTracks().forEach(track => track.stop());
        return;
      }
      attempt.stream = stream;
      const context = attempt.context = new Ctx();
      await context.resume();
      if (starting !== attempt) return;
      if (document.hidden) throw new Error("la page est en arrière-plan");
      const source = context.createMediaStreamSource(stream);
      const processor = context.createScriptProcessor(4096, 1, 1);
      const silent = context.createGain();
      silent.gain.value = 0;
      const chunks = [];
      let frames = 0;
      const frameLimit = Math.floor(context.sampleRate * 20);
      const duplexTiming = createMobileAudioTiming("websocket");
      function recordingInterrupted(error) {
        if (generation !== conversationGeneration || recording?.context !== context) return;
        finishMicPress(false);
        setStatus(error?.message || "Connexion vocale interrompue.");
      }
      if (window.JadeDuplex?.supported()) {
        const options = {
          token, session:thread, speak:soundEnabled,
          onDisconnect:recordingInterrupted,
          onEvent:async event => {
            if (generation !== conversationGeneration || activeDuplex !== duplex) return;
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
              sealReplyAudio();
              setStatus("Prête.");
            }
          }
        };
        try { duplex = window.JadeDuplex.create(options); }
        catch (_) { /* The constructor failed before sending. Keep the WAV fallback. */ }
        activeDuplex = duplex;
      }
      processor.onaudioprocess = event => {
        if (!recording || recording.context !== context) return;
        const sample = event.inputBuffer.getChannelData(0);
        const part = sample.slice(0, frameLimit - frames);
        // Only keep a WAV copy while retrying is safe. Once the socket is
        // ready, it owns this utterance and a second transport must not send it.
        if (duplex?.ready) chunks.length = 0;
        else chunks.push(part);
        frames += part.length;
        if (duplex) {
          try { duplex.push(part, context.sampleRate); }
          catch (error) {
            if (duplex.ready) return recordingInterrupted(error);
            duplex.cancel();
          }
        }
        if (frames >= frameLimit) limitRecording();
      };
      source.connect(processor);
      processor.connect(silent);
      silent.connect(context.destination);
      recording = {stream, context, source, processor, silent, chunks, duplex,
                   get frames() {return frames;}};
      starting = null;
      stream.getTracks().forEach(track => track.addEventListener?.("ended", () => {
        if (!recording?.captureClosed) recordingInterrupted(new Error("Le microphone s’est arrêté."));
      }, {once:true}));
      mic.classList.add("recording");
      mic.setAttribute("aria-pressed", "true");
      mic.setAttribute("aria-label", "Relâcher pour envoyer");
      setStatus("J’enregistre ta voix… Relâche pour envoyer.", true);
      // Avoid leaving the microphone open after 20 seconds.
      recording.timer = setTimeout(limitRecording, 20000);
    } catch (_) {
      if (starting === attempt) {
        duplex?.cancel();
        if (activeDuplex === duplex) activeDuplex = null;
        clearMicPress();
        cancelRecordingStart();
        resetMicButton();
        setStatus("Accès au micro refusé ou indisponible.");
      }
    }
  }

  function resetMicButton() {
    mic.classList.remove("recording");
    mic.setAttribute("aria-pressed", "false");
    mic.setAttribute("aria-label", "Maintenir pour parler");
    renderLiveMic();
  }

  function closeMicrophone({stream, context}) {
    stream?.getTracks().forEach(track => track.stop());
    return context?.close().catch(() => {});
  }

  function cancelRecordingStart() {
    const attempt = starting;
    starting = null;
    if (attempt) closeMicrophone(attempt);
  }

  function releaseRecording(current) {
    if (current.captureClosed) return;
    current.captureClosed = true;
    clearTimeout(current.timer);
    current.processor.onaudioprocess = null;
    for (const node of [current.source, current.processor, current.silent]) {
      try { node.disconnect(); } catch (_) {}
    }
    closeMicrophone(current);
  }

  function limitRecording() {
    if (!recording || recording.captureClosed) return;
    releaseRecording(recording);
    mic.classList.remove("recording");
    setStatus("Limite de 20 s atteinte. Relâche pour envoyer.", true);
  }

  function cancelRecording() {
    const current = recording;
    if (!current) return;
    recording = null;
    resetMicButton();
    // Backgrounding the app must discard, never send, microphone data.
    if (activeDuplex === current.duplex) activeDuplex = null;
    current.duplex?.cancel();
    releaseRecording(current);
    setStatus("Prise vocale annulée.");
  }

  async function stopRecording() {
    const current = recording;
    if (!current || busy) return;
    const generation = conversationGeneration;
    recording = null;
    busy = voicePending = true;
    // Unlock playback inside the release gesture, before network awaits.
    primeVoicePlayback();
    resetMicButton();
    mic.setAttribute("aria-label", "Interrompre la réponse vocale");
    setStatus("Je transmets ta voix à Jade…", true);
    const rate = current.context.sampleRate, frames = current.frames;
    try {
      releaseRecording(current);
      if (frames < rate / 4) {
        if (current.duplex) current.duplex.cancel();
        setStatus("Enregistrement trop court.");
        return;
      }
      if (current.duplex) {
        try {
          await current.duplex.finish();
          return;
        } catch (error) {
          if (generation !== conversationGeneration) return;
          // Before the authenticated WebSocket was ready, STT never started.
          // Once ready, NEVER retry: that could charge for a second response.
          if (current.duplex.ready) throw error;
        }
      }
      const wav = buildWav(current.chunks, rate, frames);
      await makeStreamingRequest("/api/voice", wav, {
        "Content-Type":"audio/wav",
        "X-Jade-Session":thread,
        "X-Jade-Speak":soundEnabled ? "1" : "0"
      });
    } catch (error) {
      if (generation === conversationGeneration) setStatus(error.message || "Message vocal non transmis.");
    } finally {
      if (generation === conversationGeneration) {
        if (activeDuplex === current.duplex) activeDuplex = null;
        sealReplyAudio();
        busy = voicePending = false;
        resetMicButton();
        setStatus(status.textContent);
      }
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
      linkResult.textContent = linkCommand;
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
      linkResult.textContent = linkCommand + "\nCommande copiée.";
    } catch (_) {
      linkResult.textContent = linkCommand + "\nCopie manuellement la commande.";
    }
  });

  const deploymentPanel = $("deployment-panel");
  const deploymentLoad = $("deployment-load"), deploymentRun = $("deployment-run");
  const deploymentRestart = $("deployment-restart"), deploymentState = $("deployment-state");
  const deploymentLogs = $("deployment-logs");
  const deploymentLevel = $("deployment-level");
  deploymentLevel.value = preferences?.get("deploymentLevel", "all") ?? "all";
  let deploymentPending = false, deploymentPolling = null, deploymentRawLogs = "";

  // Control runs outside Jade on Windows and stays online during a restart.
  // Tailscale Serve mounts /control to the private service on 127.0.0.1:8771.
  async function controlRequest(path, payload) {
    if (!token) throw new Error("Connecte-toi avant d’administrer Jade.");
    const response = await fetch("/control/api/" + path, {
      method:payload === undefined ? "GET" : "POST",
      cache:"no-store", credentials:"omit",
      headers:Object.assign({"Authorization":"Bearer " + token},
        payload === undefined ? {} : {"Content-Type":"application/json"}),
      ...(payload === undefined ? {} : {body:JSON.stringify(payload)})
    });
    if (response.status === 401) { authorizeAgain(); throw new Error("Jeton expiré."); }
    if (response.status === 403) throw new Error("Accès administrateur refusé par Tailscale.");
    let result;
    try { result = await response.json(); } catch (_) { throw new Error("Réponse de contrôle invalide."); }
    if (!response.ok) throw new Error(result.error || "Contrôleur Windows indisponible.");
    return result;
  }

  function renderDeploymentLogs() {
    let lines = deploymentRawLogs.split("\n");
    if (deploymentLevel.value === "error")
      lines = lines.filter(line => /\b(ERROR|CRITICAL|Traceback|Exception)\b/i.test(line));
    else if (deploymentLevel.value === "warning")
      lines = lines.filter(line => /\b(WARNING|ERROR|CRITICAL|Traceback|Exception)\b/i.test(line));
    deploymentLogs.textContent = lines.join("\n") || "Aucune ligne correspondant au filtre.";
    deploymentLogs.scrollTop = deploymentLogs.scrollHeight;
  }

  async function refreshDeployment() {
    if (!token || !deploymentPanel.open || document.hidden || deploymentPending) return;
    try {
      const [state, result] = await Promise.all([
        controlRequest("status"), controlRequest("logs")
      ]);
      const phase = state.phase || "inconnu";
      const live = state.running ? "En cours" : "Arrêtée";
      const pycharm = state.pycharm_run ? "Run ouvert" : "PyCharm non connecté";
      deploymentState.textContent = "Jade : " + live + " · " + pycharm +
        " · " + (state.branch || "branche inconnue") + " " +
        (state.sha ? String(state.sha).slice(0, 8) : "(version inconnue)") +
        " · " + phase +
        (state.target_sha ? " · Distant (dernier fetch) : " + String(state.target_sha).slice(0, 8) : "") +
        ({updated:" · Mise à jour réussie", already_current:" · Déjà à jour",
          restarted:" · Redémarrage seul réussi", failed:" · Opération échouée"}[state.result] || "") +
        (state.error ? " · Erreur : " + state.error : "");
      deploymentRestart.disabled = !state.pycharm_run || phase !== "idle";
      deploymentRun.disabled = deploymentRestart.disabled || state.branch !== "develop";
      deploymentRawLogs = typeof result.text === "string" ? result.text : "";
      renderDeploymentLogs();
    } catch (error) {
      deploymentState.textContent = error.message || "Contrôleur indisponible.";
      deploymentRun.disabled = deploymentRestart.disabled = true;
    }
  }

  async function submitDeployment(operation) {
    if (deploymentPending || !token) return;
    if (!window.confirm(operation === "update"
      ? "Mettre à jour develop et redémarrer la Jade exécutée dans PyCharm ?"
      : "Redémarrer la Jade exécutée dans PyCharm sans mise à jour ?")) return;
    deploymentPending = true;
    deploymentRun.disabled = deploymentRestart.disabled = true;
    deploymentState.textContent = "Demande envoyée au contrôleur Windows…";
    try {
      await controlRequest(operation, {confirm:true});
      deploymentState.textContent = "Opération demandée. Suivi dans cette console jusqu’à la reprise.";
    } catch (error) {
      deploymentState.textContent = error.message || "Opération refusée.";
    } finally {
      deploymentPending = false;
      refreshDeployment();
    }
  }

  deploymentPanel.addEventListener("toggle", () => {
    if (deploymentPolling !== null) {
      window.clearInterval(deploymentPolling);
      deploymentPolling = null;
    }
    if (deploymentPanel.open) {
      refreshDeployment();
      deploymentPolling = window.setInterval(refreshDeployment, 3000);
    }
  });
  deploymentLoad.addEventListener("click", refreshDeployment);
  deploymentLevel.addEventListener("change", () => {
    preferences?.set("deploymentLevel", deploymentLevel.value);
    renderDeploymentLogs();
  });
  deploymentRun.addEventListener("click", () => submitDeployment("update"));
  deploymentRestart.addEventListener("click", () => submitDeployment("restart"));

  const discordLivePanel = $("discord-live-panel"), discordLiveToggle = $("discord-live-enabled");
  const discordLiveMinutes = $("discord-live-minutes"), discordLiveStatus = $("discord-live-status");
  const discordMinutesFormat = new Intl.NumberFormat("fr-FR", {maximumFractionDigits:2});
  let discordLiveEnabled = null, discordLiveRequest = null;
  function resetDiscordLivePanel() {
    discordLiveRequest?.abort();
    discordLiveRequest = discordLiveEnabled = null;
    if (!discordLiveToggle) return;
    discordLiveToggle.checked = true;
    discordLiveToggle.disabled = true;
    discordLiveMinutes.textContent = "—";
    discordLiveStatus.hidden = true;
  }
  async function refreshDiscordLive(enabled) {
    if (!token || discordLiveRequest || (enabled !== undefined && discordLiveEnabled === null)) return;
    const controller = new AbortController();
    discordLiveRequest = controller;
    discordLiveToggle.disabled = true;
    const body = enabled === undefined ? undefined : JSON.stringify({enabled});
    try {
      const result = await makeRequest("/api/discord/live", body,
        body === undefined ? undefined : {"Content-Type":"application/json"}, controller.signal);
      if (controller.signal.aborted) return;
      if (typeof result?.enabled !== "boolean") throw new Error("Suivi Discord indisponible.");
      discordLiveEnabled = result.enabled;
      const recorded = Number.isFinite(result.minutes) && result.minutes >= 0;
      discordLiveMinutes.textContent = recorded ? discordMinutesFormat.format(result.minutes) : "—";
      discordLiveStatus.textContent = recorded
        ? (result.partial ? "Relevé partiel pour ce mois." : "")
        : "Relevé indisponible.";
    } catch (_) {
      if (controller.signal.aborted) return;
      discordLiveStatus.textContent = enabled === undefined
        ? "Impossible de charger le suivi Discord."
        : "Impossible de confirmer le changement. Réessaie.";
    } finally {
      if (discordLiveRequest === controller) {
        discordLiveRequest = null;
        discordLiveToggle.checked = discordLiveEnabled ?? true;
        discordLiveToggle.disabled = discordLiveEnabled === null;
        discordLiveStatus.hidden = !discordLiveStatus.textContent;
      }
    }
  }
  discordLivePanel?.addEventListener("toggle", () => {
    if (discordLivePanel.open) refreshDiscordLive();
  });
  discordLiveToggle?.addEventListener("change", () => refreshDiscordLive(discordLiveToggle.checked));

  const billingPanel = $("billing-panel");
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
    try {
      const result = await makeRequest("/api/billing", JSON.stringify({refresh}), {"Content-Type":"application/json"});
      if (result.status === "ok" || result.status === "stale") {
        billingToday.textContent = formatCosts(result.today);
        billingMonth.textContent = formatCosts(result.month);
        const checkedAt = new Date(result.checked_at);
        const checked = result.checked_at && Number.isFinite(checkedAt.getTime())
          ? checkedAt.toLocaleString("fr-FR") : "—";
        billingStatus.textContent = `Dernière actualisation : ${checked}`;
      } else {
        billingToday.textContent = billingMonth.textContent = "—";
        billingStatus.textContent = "Dernière actualisation : —";
      }
    } catch (_) {
      // Keep the last dated snapshot when a refresh fails. No successful
      // update time is invented and unavailable amounts remain unspecified.
    } finally {
      billingPending = false;
    }
  }
  billingPanel.addEventListener("toggle", () => { if (billingPanel.open) loadBilling(); });
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
  const notificationToggle = $("notifications-enabled");
  let confirmedNotificationChoice = preferences?.get("notificationsEnabled", false) ? "on" : "off";
  let notificationBusy = false;
  let notificationReadVersion = 0;
  function showNotificationChoice(value) {
    notificationToggle.checked = value === "on";
  }
  function lockNotificationChoice(value) {
    notificationToggle.disabled = value;
  }
  function showNotificationMessage(message = "") {
    notificationStatus.textContent = message;
    notificationStatus.hidden = !message;
  }
  showNotificationChoice(confirmedNotificationChoice);
  // Refresh from browser state. Never prompt for permission while rendering the page.
  async function refreshNotificationChoice() {
    if (!token || notificationBusy) return;
    const version = ++notificationReadVersion;
    try {
      const registration = await registrationForPush();
      const subscription = await registration.pushManager.getSubscription();
      if (version !== notificationReadVersion || notificationBusy) return;
      confirmedNotificationChoice = subscription && Notification.permission === "granted" ? "on" : "off";
      preferences?.set("notificationsEnabled", confirmedNotificationChoice === "on");
      showNotificationChoice(confirmedNotificationChoice);
      lockNotificationChoice(false);
      showNotificationMessage();
    } catch (error) {
      if (version !== notificationReadVersion || notificationBusy) return;
      showNotificationChoice(confirmedNotificationChoice);
      lockNotificationChoice(true);
      showNotificationMessage("Notifications indisponibles : " + error.message);
    }
  }
  async function changeNotificationChoice(enable) {
    if (notificationBusy) return;
    if (!token) { showNotificationChoice(confirmedNotificationChoice); authorizeAgain(); return; }
    notificationBusy = true;
    notificationReadVersion++;
    lockNotificationChoice(true);
    showNotificationMessage();
    let createdSubscription = null;
    try {
      const registration = await registrationForPush();
      if (enable) {
        const config = await makeRequest("/api/push", JSON.stringify({action:"config"}), reminderHeaders);
        if (!config.enabled) throw new Error("Push non configuré sur le PC Jade.");
        if (await Notification.requestPermission() !== "granted")
          throw new Error("Permission de notifications refusée.");
        let subscription = await registration.pushManager.getSubscription();
        if (!subscription) {
          subscription = await registration.pushManager.subscribe({
            userVisibleOnly:true, applicationServerKey:decodeVapidKey(config.vapid_public_key)
          });
          createdSubscription = subscription;
        }
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
      preferences?.set("notificationsEnabled", enable);
      showNotificationChoice(confirmedNotificationChoice);
      showNotificationMessage();
    } catch (error) {
      // A browser subscription without the matching server registration is
      // not an enabled setting. Remove only a subscription created by this try.
      if (createdSubscription) {
        try { await createdSubscription.unsubscribe(); } catch (_) {}
      }
      showNotificationChoice(confirmedNotificationChoice);
      showNotificationMessage((enable ? "Activation impossible : " : "Désactivation incomplète : ") + error.message);
    } finally {
      notificationBusy = false;
      lockNotificationChoice(false);
    }
  }
  notificationToggle.addEventListener("change", () => changeNotificationChoice(notificationToggle.checked));

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
  mic.addEventListener("pointerdown", event => {
    if (mic.disabled || liveClient?.mode === "live" || event.button !== 0 || event.isPrimary === false) return;
    event.preventDefault();
    return startRecording({pointerId:event.pointerId});
  });
  mic.addEventListener("click", () => {
    if (mic.disabled || liveClient?.mode !== "live") return;
    if (shell.dataset.view === "home" || shell.classList.contains("is-room-only")) {
      return liveClient.toggleMicrophone();
    }
  });
  window.addEventListener("pointerup", event => {
    if (micPress?.pointerId === event.pointerId) finishMicPress(true);
  }, true);
  window.addEventListener("pointercancel", event => {
    if (micPress?.pointerId === event.pointerId) finishMicPress(false);
  }, true);
  mic.addEventListener("lostpointercapture", event => {
    if (micPress?.pointerId === event.pointerId) finishMicPress(false);
  });
  mic.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      if (voicePending) {
        cancelConversation();
        setStatus("Réponse vocale interrompue.");
      } else finishMicPress(false);
      return;
    }
    if (liveClient?.mode === "live" || (event.key !== " " && event.key !== "Enter")) return;
    event.preventDefault();
    if (mic.disabled) return;
    if (!event.repeat) return startRecording({key:event.key});
  });
  mic.addEventListener("keyup", event => {
    if (micPress?.key !== event.key) return;
    event.preventDefault();
    finishMicPress(true);
  });
  mic.addEventListener("blur", () => {
    if (micPress?.key !== undefined) finishMicPress(false);
  });
  mic.addEventListener("contextmenu", event => {
    if (micPress || liveClient?.mode === "live") event.preventDefault();
  });
  window.addEventListener("blur", () => finishMicPress(false));
  window.addEventListener("offline", () => {
    if (!micPress && !voicePending && !liveClient?.active) return;
    cancelConversation("offline");
    setStatus("Connexion interrompue pendant le tour vocal.");
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      const interrupted = Boolean(starting || busy || recording || liveClient?.active);
      cancelConversation("background");
      if (interrupted && !modelChanging) setStatus("Conversation interrompue.");
    } else if (token && shell.dataset.view === "reminders") {
      loadReminders();
    }
  });
  window.addEventListener("pagehide", cancelConversation);
  soundToggle.addEventListener("change", () => {
    soundEnabled = soundToggle.checked;
    preferences?.set("soundEnabled", soundEnabled);
    if (!soundEnabled) {
      liveClient?.stop("sound_off");
      stopPlayback();
    }
    if (liveState) renderLiveState(liveState);
  });
  newChat.addEventListener("click", () => {
    if (modelChanging || busy || recording || starting) return;
    cancelConversation("new_thread");
    thread = newThread();
    stopPlayback();
    log.replaceChildren();
    liveTranscripts.clear();
    setStatus("Nouveau fil.");
  });
  const fullscreenButton = $("fullscreen");
  const roomPlane = document.querySelector(".room-plane");
  const scene = document.querySelector(".room");
  let nativeRoomFullscreen = false;
  let fullscreenPending = false;
  let scenePointer = null, previousSceneTap = null;
  let lastTouchTime = -Infinity;
  const sceneControls = "button,a,input,select,textarea,label,summary,[role='button'],[contenteditable],.room-picker";
  const isSceneControl = target => Boolean(target?.closest?.(sceneControls));
  function resetSceneGesture() {
    scenePointer = null;
    previousSceneTap = null;
  }
  function setRoomFullscreen(active) {
    resetSceneGesture();
    // Freeze the 4:3 background width before its enclosing viewport expands.
    if (active && roomPlane) {
      const width = roomPlane.getBoundingClientRect().width;
      if (width > 0) shell.style.setProperty("--room-immersive-width", width + "px");
    }
    shell.classList.toggle("is-room-only", active);
    syncMicPlacement();
    if (!active) shell.style.removeProperty("--room-immersive-width");
    const description = active ? "Quitter le plein écran" : "Afficher uniquement Jade en plein écran";
    fullscreenButton.setAttribute("aria-label", description);
    fullscreenButton.setAttribute("title", description);
    fullscreenButton.setAttribute("aria-pressed", String(active));
    window.JadeAvatar?.resize?.();
  }
  async function toggleRoomFullscreen() {
    // A native fullscreen transition may outlive a click. Keep repeated input
    // from starting a competing request/exit while the browser is settling.
    if (fullscreenPending) {
      resetSceneGesture();
      return;
    }
    fullscreenPending = true;
    try {
      if (shell.classList.contains("is-room-only")) {
        setRoomFullscreen(false);
        if (document.fullscreenElement === shell) {
          try { await document.exitFullscreen?.(); } catch (_) { /* CSS view already closed */ }
        }
        return;
      }
      setRoomFullscreen(true);
      if (shell.requestFullscreen) {
        try { await shell.requestFullscreen(); } catch (_) { /* CSS fullscreen stays available */ }
      }
    } finally {
      fullscreenPending = false;
    }
  }
  fullscreenButton.addEventListener("click", toggleRoomFullscreen);
  scene?.addEventListener("dblclick", event => {
    // Touch browsers can also emit a compatibility dblclick after pointerup.
    if (window.JadeAvatarGestures?.shouldIgnoreFullscreenTap?.(event) ||
        event.defaultPrevented || event.button !== 0 || isSceneControl(event.target) ||
        event.sourceCapabilities?.firesTouchEvents || event.timeStamp - lastTouchTime < 800) return;
    event.preventDefault();
    void toggleRoomFullscreen();
  });
  scene?.addEventListener("pointerdown", event => {
    if (event.pointerType !== "touch" && event.pointerType !== "pen") return;
    lastTouchTime = event.timeStamp;
    if (event.defaultPrevented || event.isPrimary === false || scenePointer || isSceneControl(event.target)) {
      resetSceneGesture();
      return;
    }
    scenePointer = {id:event.pointerId, x:event.clientX, y:event.clientY, time:event.timeStamp,
      view:shell.dataset.view, immersive:shell.classList.contains("is-room-only")};
  });
  scene?.addEventListener("pointermove", event => {
    if (scenePointer?.id === event.pointerId &&
        Math.hypot(event.clientX - scenePointer.x, event.clientY - scenePointer.y) > 12)
      resetSceneGesture();
  });
  scene?.addEventListener("pointerup", event => {
    if (event.pointerType !== "touch" && event.pointerType !== "pen") return;
    lastTouchTime = event.timeStamp;
    if (window.JadeAvatarGestures?.shouldIgnoreFullscreenTap?.(event)) {
      resetSceneGesture();
      return;
    }
    const pointer = scenePointer;
    scenePointer = null;
    if (!pointer || pointer.id !== event.pointerId || event.defaultPrevented ||
        isSceneControl(event.target) || event.timeStamp - pointer.time > 300 ||
        Math.hypot(event.clientX - pointer.x, event.clientY - pointer.y) > 12 ||
        pointer.view !== shell.dataset.view || pointer.immersive !== shell.classList.contains("is-room-only")) {
      previousSceneTap = null;
      return;
    }
    const previous = previousSceneTap;
    previousSceneTap = {x:event.clientX, y:event.clientY, time:event.timeStamp,
      view:pointer.view, immersive:pointer.immersive};
    if (previous && event.timeStamp - previous.time <= 350 &&
        Math.hypot(event.clientX - previous.x, event.clientY - previous.y) <= 32 &&
        previous.view === pointer.view && previous.immersive === pointer.immersive) {
      event.preventDefault();
      void toggleRoomFullscreen();
    }
  });
  scene?.addEventListener("pointercancel", resetSceneGesture);
  // A second finger outside the scene must also cancel a possible double tap.
  document.addEventListener("pointerdown", event => {
    if (event.isPrimary === false || !scene?.contains(event.target)) resetSceneGesture();
  }, true);
  document.addEventListener("scroll", resetSceneGesture, true);
  window.addEventListener("blur", resetSceneGesture);
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
  window.JadeConversation = {stopForModelChange};
  window.JadeMobileApp = {
    liveModuleReady:initializeLive,
    liveModuleFailed,
    liveModuleLoading() { liveLoadMessage = ""; renderLiveAvailability(); },
    login(value) {
      resetLiveAuthentication("auth_changed");
      token = value;
      authInput.value = "";
      authFeedback.textContent = "";
      modal.classList.add("hidden");
      connection.textContent = "Connectée à Jade";
      connection.classList.add("online");
      setStatus("Connexion vérifiée. Tu peux parler ou écrire à Jade.");
      renderLiveAvailability();
      initializeLive();
      // Do not display the Android keyboard on the room-first landing page.
      openReminderFromHash();
      if (shell.dataset.view === "reminders") {
        loadReminders();
      }
      if (shell.dataset.view === "profile") {
        refreshNotificationChoice();
        if (discordLivePanel?.open) refreshDiscordLive();
      }
    }
  };
})();
