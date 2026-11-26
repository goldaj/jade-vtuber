/* Private mobile GPT-Live: local capture lease, WebRTC media, authenticated
 * Jade control channel. The browser holds no provider key and sends no model
 * commands. Bearer and pre-roll exist only in memory. */
"use strict";
(() => {
  function create(options = {}) {
    const env = options.environment || window;
    const doc = env.document || document;
    const nav = env.navigator || navigator;
    const clock = () => env.performance?.now?.() ?? performance.now();
    const later = (fn, ms) => env.setTimeout(fn, ms);
    const cancelLater = id => { if (id !== null) env.clearTimeout(id); };
    const callbacks = (name, ...args) => { try { options[name]?.(...args); } catch (_) {} };
    const clientId = "live-" + (env.crypto || crypto).randomUUID();
    const AudioConstructor = env.AudioContext || env.webkitAudioContext;
    const availableBrowser = Boolean(AudioConstructor && env.AudioWorkletNode &&
      env.RTCPeerConnection && env.WebSocket && nav.mediaDevices?.getUserMedia && env.isSecureContext !== false);
    const state = {mode:"classic", revision:-1, loaded:false, supported:availableBrowser,
      available:false, capabilities:null, capture:"closed", lease_state:"closed",
      session_state:"absent", session_id:null, reason:"", message:"", changing:false};
    let epoch = 0, preferenceRequest = 0, requestedMode = null;
    let leaseId = null, leaseThread = null, socket = null, controlReady = false;
    let heartbeatTimer = null, heartbeatSeq = 0, acknowledgedSeq = 0, lastAck = 0, lastHeartbeat = 0;
    let context = null, media = null, source = null, worklet = null, destination = null;
    let peer = null, dataChannel = null, remoteSource = null, analyser = null, playbackFrame = null;
    let openingTimer = null, drainTimer = null, disconnectTimer = null;
    let opening = false, speechActive = false, playbackActive = false, lastAudible = -Infinity;
    let pendingResponse = false, sentSpeech = false, closePromise = null, heldSession = null;
    let pendingWake = false, wakeStarted = null;
    let modeForcedOff = false;
    const snapshot = () => ({...state, active:Boolean(leaseId || state.capture !== "closed"),
      media_state:peer ? (opening ? "connecting" : "connected") : "absent",
      playback_active:playbackActive, speech_active:speechActive});
    const publish = () => callbacks("onState", snapshot());
    const message = (reason, text) => { state.reason = reason; state.message = text; publish(); };
    const leaseMs = () => Math.max(1000, Number(state.capabilities?.lease_seconds || 5) * 1000);
    const heartbeatMs = () => Math.max(250, Number(state.capabilities?.heartbeat_seconds || 2) * 1000);
    function assertCurrent(generation) {
      if (generation !== epoch || !leaseId || state.mode !== "live" || doc.hidden)
        throw new Error("live_cancelled");
    }
    async function request(path, body, timeout = 5000, bearer = options.getToken?.()) {
      if (!bearer) throw new Error("Accès mobile expiré.");
      const controller = new (env.AbortController || AbortController)();
      const timer = later(() => controller.abort(), timeout);
      try {
        const response = await (env.fetch || fetch)(path, {method:body === undefined ? "GET" : "POST",
          mode:"same-origin", credentials:"omit", cache:"no-store", signal:controller.signal,
          headers:{Authorization:"Bearer " + bearer, "Content-Type":"application/json"},
          ...(body === undefined ? {} : {body:JSON.stringify(body)})});
        const result = await response.json().catch(() => ({}));
        if (!response.ok) {
          const reasons = {
            microphone_owned_by_other_client:"Le micro Live est déjà ouvert sur un autre appareil.",
            previous_session_not_closed:"La conversation Live précédente se ferme encore. Réessaie dans quelques instants.",
            close_unconfirmed:"Jade vérifie encore la fermeture distante. Vérifie son état depuis Profil.",
            creation_unconfirmed:"Jade vérifie encore la connexion distante. Vérifie son état depuis Profil.",
            live_budget_insufficient:"Le budget Live disponible ne permet pas une nouvelle conversation.",
            live_budget_unavailable:"Le budget Live n’est pas disponible pour le moment.",
            live_budget_exhausted:"Le budget Live est atteint. Le mode classique reste disponible.",
            live_mode_off:"Le mode Live a été désactivé. Vérifie le choix dans Profil.",
            invalid_or_expired_live_lease:"L’autorisation du micro a expiré. Touche-le pour reprendre.",
          };
          const error = new Error(result.message || reasons[result.code || result.error] || "Live momentanément indisponible.");
          error.status = response.status;
          error.result = result;
          if (response.status === 401 || response.status === 403) callbacks("onAuthFailure");
          throw error;
        }
        return result;
      } finally { cancelLater(timer); }
    }
    function preference(value) {
      const revision = Number(value?.revision);
      if (!Number.isSafeInteger(revision) || revision < state.revision ||
          !["live", "classic"].includes(value?.mode)) return;
      const off = value.mode === "classic";
      state.revision = revision;
      state.loaded = true;
      state.mode = requestedMode === "classic" || modeForcedOff ? "classic" : value.mode;
      if (off && (leaseId || state.capture !== "closed")) void stop("preference_off");
      publish();
    }
    async function refresh() {
      const results = await Promise.allSettled([
        request("/api/live/capabilities"), request("/api/voice/preferences")]);
      if (results[0].status === "fulfilled") {
        state.capabilities = results[0].value;
        state.available = Boolean(availableBrowser && state.capabilities.enabled && state.capabilities.available);
        if (!state.available) state.reason = state.capabilities.reason || "unavailable";
        // Read-only reconciliation after an uncertain close. A snapshot from
        // another client never transfers its lease or authorizes capture here.
        const observed = state.capabilities.state;
        if (!leaseId && state.capture === "closed" && !closePromise && observed?.session_state === "absent") {
          state.session_state = "absent";
          state.session_id = null;
          if (state.available) state.reason = state.message = "";
        }
      }
      if (results[1].status === "fulfilled") preference(results[1].value);
      else state.message = "Le choix vocal n’a pas pu être vérifié. Réessaie depuis Profil.";
      publish();
      return snapshot();
    }
    async function setMode(mode) {
      if (!["classic", "live"].includes(mode)) return false;
      const turn = ++preferenceRequest;
      requestedMode = mode;
      modeForcedOff = mode === "classic";
      state.changing = true;
      if (mode === "classic") { state.mode = "classic"; void stop("preference_off"); }
      publish();
      try {
        if (!state.loaded) await refresh();
        if (turn !== preferenceRequest) return false;
        let result;
        try { result = await request("/api/voice/preferences", {mode, revision:state.revision}); }
        catch (error) {
          const current = error.result?.preference || error.result?.state || error.result;
          if (error.status === 409 && mode === "classic" && turn === preferenceRequest &&
              Number.isSafeInteger(Number(current?.revision))) {
            state.revision = Math.max(state.revision, Number(current.revision));
            result = await request("/api/voice/preferences", {mode, revision:state.revision});
          } else {
            if (error.status === 409) preference(current);
            throw error;
          }
        }
        if (turn !== preferenceRequest) return false;
        requestedMode = null;
        modeForcedOff = false;
        preference(result);
        state.message = "";
        state.reason = "";
        return state.mode === mode;
      } catch (error) {
        if (turn === preferenceRequest) {
          state.message = mode === "classic" ? "Micro coupé. La désactivation doit encore être confirmée par Jade." :
            (error.status === 409 ? "Le choix a changé sur un autre appareil. Vérifie Profil." : error.message);
        }
        return false;
      } finally {
        if (turn === preferenceRequest) { requestedMode = null; state.changing = false; publish(); }
      }
    }
    function sendControl(value) {
      if (!controlReady || socket?.readyState !== 1) return false;
      try { socket.send(JSON.stringify(value)); return true; } catch (_) { return false; }
    }
    function observePlayback(kind) {
      if (heldSession) sendControl({type:"playback", session_id:heldSession, state:kind});
    }
    function heartbeat(submittedSpeech = false) {
      if (!controlReady) return;
      lastHeartbeat = clock();
      sendControl({type:"heartbeat", seq:++heartbeatSeq, visible:!doc.hidden,
        capture:state.capture === "armed" ? "armed" : "closed",
        playback_active:playbackActive, speech_active:submittedSpeech || speechActive});
    }
    function stopCapture() {
      state.capture = "closed";
      speechActive = false;
      for (const stream of [media, destination?.stream])
        for (const track of stream?.getTracks?.() || []) { try { track.stop(); } catch (_) {} }
      if (worklet) {
        worklet.port.onmessage = null;
        try { worklet.port.postMessage({type:"stop"}); } catch (_) {}
      }
      try { source?.disconnect(); } catch (_) {}
      try { worklet?.disconnect(); } catch (_) {}
      media = source = worklet = destination = null;
      for (const sender of peer?.getSenders?.() || []) {
        if (sender.track?.kind !== "audio") continue;
        try { Promise.resolve(sender.replaceTrack(null)).catch(() => {}); } catch (_) {}
      }
    }
    function stopOutput(interrupted = true) {
      if (interrupted && (playbackActive || pendingResponse)) {
        observePlayback("interrupted");
        callbacks("onInterruption", heldSession, playbackActive ? "interrupted" : "delivery_unknown");
      }
      if (playbackFrame !== null) env.cancelAnimationFrame(playbackFrame);
      playbackFrame = null;
      try { remoteSource?.disconnect(); analyser?.disconnect(); } catch (_) {}
      remoteSource = analyser = null;
      playbackActive = false;
      lastAudible = -Infinity;
      callbacks("onPlayback", 0, false);
    }
    function closePeer(interrupted = true) {
      cancelLater(openingTimer); openingTimer = null;
      cancelLater(disconnectTimer); disconnectTimer = null;
      opening = false;
      stopOutput(interrupted);
      const old = peer;
      peer = null;
      if (old) {
        old.ontrack = old.onconnectionstatechange = old.oniceconnectionstatechange = null;
        try { old.close(); } catch (_) {}
      }
      if (dataChannel) {
        dataChannel.onmessage = dataChannel.onclose = null;
        try { dataChannel.close(); } catch (_) {}
      }
      dataChannel = null;
      heldSession = null;
      if (!pendingWake) wakeStarted = null;
      pendingResponse = sentSpeech = false;
      state.session_id = null;
    }
    function releaseAudio() {
      stopCapture();
      closePeer();
      if (context) {
        context.onstatechange = null;
        Promise.resolve(context.close()).catch(() => {});
      }
      context = null;
    }
    function closeControl() {
      if (heartbeatTimer !== null) env.clearInterval(heartbeatTimer);
      heartbeatTimer = null;
      controlReady = false;
      if (socket) {
        socket.onopen = socket.onmessage = socket.onclose = socket.onerror = null;
        socket.close();
      }
      socket = null;
    }
    function finishLease(reason, sessionState = "absent") {
      cancelLater(drainTimer); drainTimer = null;
      epoch++;
      releaseAudio();
      closeControl();
      leaseId = leaseThread = null;
      pendingWake = false; wakeStarted = null;
      state.lease_state = "closed";
      state.session_state = sessionState === "closing" ? "close_unconfirmed" : sessionState;
      state.reason = reason || state.reason;
      if (["opening_unknown", "close_unconfirmed"].includes(state.session_state)) {
        state.available = false;
        state.message = "Micro coupé. Jade vérifie encore la connexion distante. Vérifie son état depuis Profil avant de reprendre.";
      }
      publish();
    }
    function acceptSnapshot(value, generation) {
      if (!value || generation !== epoch) return;
      if (value.session_state === "closed") value = {...value, session_state:"absent"};
      preference(value);
      if (generation !== epoch || !leaseId) return;
      if (value.lease_id && value.lease_id !== leaseId) return;
      if (value.lease_state) state.lease_state = value.lease_state;
      if (value.session_state) state.session_state = value.session_state;
      if (value.reason) state.reason = value.reason;
      if (value.session_id) { state.session_id = value.session_id; heldSession ||= value.session_id; }
      if (value.lease_state === "closed" || value.lease_state === "expired") {
        finishLease(value.reason, value.session_state || "absent");
        return;
      }
      if (value.lease_state === "draining") stopCapture();
      if (value.session_state === "closing" && state.lease_state === "armed" && peer) {
        closePeer(false);
        worklet?.port.postMessage({type:"local"});
      }
      if (value.session_state === "absent" && (!opening || heldSession) && (peer || heldSession)) {
        closePeer(false);
        if (state.capture === "armed" && !pendingWake) worklet?.port.postMessage({type:"local"});
      }
      if (["close_unconfirmed", "opening_unknown"].includes(value.session_state)) {
        // A missing provider terminal must never leave a local microphone or
        // a second media generation running while the server reconciles it.
        state.message = "Micro coupé. Jade vérifie encore l’état de la connexion distante.";
        finishLease(value.reason || value.session_state, value.session_state);
        return;
      }
      if (value.session_state === "absent" && pendingWake && state.capture === "armed") {
        pendingWake = false;
        void openSession(generation);
      }
      publish();
    }
    function connectControl(generation) {
      return new Promise((resolve, reject) => {
        const location = env.location;
        const url = (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/api/live/control";
        const ws = new env.WebSocket(url, "jade-live-v1");
        socket = ws;
        let settled = false;
        const timeout = later(() => failed(new Error("La supervision Live ne répond pas.")), leaseMs());
        function failed(error) {
          cancelLater(timeout);
          if (!settled) { settled = true; reject(error); }
          if (generation === epoch && leaseId) void stop("control_lost", {message:error.message});
        }
        ws.onopen = () => {
          if (generation !== epoch) { ws.close(); return; }
          ws.send(JSON.stringify({type:"auth", token:options.getToken?.(), client_id:clientId,
            thread_id:leaseThread, lease_id:leaseId}));
        };
        ws.onerror = () => failed(new Error("Connexion Live interrompue."));
        ws.onclose = () => failed(new Error("Supervision Live interrompue. Touche le micro pour reprendre."));
        ws.onmessage = ({data}) => {
          if (generation !== epoch || socket !== ws) return;
          let event;
          try { event = JSON.parse(data); } catch (_) { return; }
          if (event.type === "ready") {
            if (settled || controlReady) return;
            controlReady = true;
            lastAck = lastHeartbeat = clock();
            heartbeatSeq = acknowledgedSeq = 0;
            acceptSnapshot(event.state || event, generation);
            if (generation !== epoch || !leaseId) { failed(new Error("Armement Live refusé.")); return; }
            settled = true;
            cancelLater(timeout);
            heartbeatTimer = env.setInterval(() => {
              if (generation !== epoch) return;
              if (clock() - lastAck >= leaseMs()) {
                void stop("heartbeat_timeout", {message:"Jade ne confirme plus la connexion. Micro coupé."});
                return;
              }
              if (clock() - lastHeartbeat < heartbeatMs()) return;
              heartbeat();
            }, Math.min(250, heartbeatMs()));
            resolve();
          } else if (event.type === "state") {
            const seq = Number(event.seq);
            if (Number.isSafeInteger(seq) && seq > acknowledgedSeq && seq <= heartbeatSeq) {
              acknowledgedSeq = seq;
              lastAck = clock();
            }
            acceptSnapshot(event.state || event, generation);
          } else if (event.type === "preference") preference(event);
          else if (event.type === "incident") {
            state.message = event.message || "La conversation Live a été interrompue.";
            state.reason = event.code || "incident";
            publish();
            if (event.fatal !== false) void stop(state.reason, {message:state.message});
          } else if (event.session_id && event.session_id === heldSession) {
            if (event.type === "transcript" || event.type === "live_transcript") callbacks("onTranscript", event);
            else if (event.type === "attachments") callbacks("onAttachments", event);
            else if (event.type === "intent") callbacks("onIntent", event.intent || "neutral");
          }
        };
      });
    }
    function installOutput(stream, generation, connection) {
      if (generation !== epoch || peer !== connection || !context || !options.getSoundEnabled?.()) return;
      stopOutput(false);
      remoteSource = context.createMediaStreamSource(stream);
      analyser = context.createAnalyser();
      analyser.fftSize = 512;
      remoteSource.connect(analyser);
      analyser.connect(context.destination);
      const samples = new Float32Array(analyser.fftSize);
      function animate() {
        if (generation !== epoch || peer !== connection || !analyser) return;
        analyser.getFloatTimeDomainData(samples);
        let power = 0;
        for (const sample of samples) power += sample * sample;
        const level = Math.sqrt(power / samples.length);
        if (level > .006) lastAudible = clock();
        const playing = clock() - lastAudible < 200;
        if (playing && !playbackActive) observePlayback("playing");
        playbackActive = playing;
        callbacks("onPlayback", Math.min(1, level * 7), playing);
        playbackFrame = env.requestAnimationFrame(animate);
      }
      animate();
    }
    async function openSession(generation) {
      if (opening || peer || state.capture !== "armed" || state.lease_state !== "armed") return;
      if (wakeStarted === null) wakeStarted = clock();
      if (["closing", "close_unconfirmed", "opening_unknown"].includes(state.session_state)) {
        pendingWake = true;
        return;
      }
      opening = true;
      pendingResponse = true;
      callbacks("onIntent", "neutral");
      state.session_state = "opening";
      state.message = "";
      publish();
      openingTimer = later(() => {
        if (generation === epoch && opening) void stop("opening_timeout",
          {message:"La connexion a pris trop de temps. Touche le micro et répète ta phrase."});
      }, Math.max(0, Math.min(8000, Number(state.capabilities?.opening_timeout_seconds || 8) * 1000) - (clock() - wakeStarted)));
      let connection;
      try {
        connection = new env.RTCPeerConnection();
        peer = connection;
        for (const track of destination.stream.getAudioTracks()) connection.addTrack(track, destination.stream);
        // Official GPT-Live WebRTC channel. allowed_client_events is empty on
        // the server: no session.start, response.create or audio.append here.
        dataChannel = connection.createDataChannel("oai-events");
        dataChannel.onmessage = ({data}) => {
          if (generation !== epoch || peer !== connection) return;
          let event;
          try { event = JSON.parse(data); } catch (_) { return; }
          if (event.type === "session.closed") {
            // The server may close an idle remote generation while preserving
            // the local arm lease. Await its authoritative terminal snapshot.
            closePeer(false);
            state.session_state = "closing";
            if (state.capture === "armed") worklet?.port.postMessage({type:"local"});
            publish();
          }
        };
        connection.ontrack = event => {
          const stream = event.streams?.[0] || new env.MediaStream([event.track]);
          installOutput(stream, generation, connection);
          if (event.track) event.track.onended = () => {
            if (generation === epoch && peer === connection) void stop("media_ended");
          };
        };
        const connectionChanged = () => {
          if (generation !== epoch || peer !== connection) return;
          const failed = [connection.connectionState, connection.iceConnectionState]
            .some(value => ["failed", "disconnected", "closed"].includes(value));
          if (failed) { void stop("media_lost", {message:"La liaison audio est interrompue. Micro coupé."}); return; }
          if (connection.connectionState === "connected" ||
              ["connected", "completed"].includes(connection.iceConnectionState)) {
            if (!opening) return;
            opening = false;
            wakeStarted = null;
            cancelLater(openingTimer); openingTimer = null;
            worklet?.port.postMessage({type:"connected"});
            state.session_state = "active";
            publish();
          }
        };
        connection.onconnectionstatechange = connection.oniceconnectionstatechange = connectionChanged;
        const offer = await connection.createOffer();
        assertCurrent(generation);
        await connection.setLocalDescription(offer);
        assertCurrent(generation);
        const result = await request("/api/live/sessions", {client_id:clientId, thread_id:leaseThread,
          lease_id:leaseId, request_id:(env.crypto || crypto).randomUUID(), sdp:connection.localDescription?.sdp || offer.sdp}, 8000);
        assertCurrent(generation);
        if (peer !== connection || !result.session_id || !result.sdp) throw new Error("Réponse Live incomplète.");
        heldSession = state.session_id = result.session_id;
        await connection.setRemoteDescription({type:"answer", sdp:result.sdp});
        assertCurrent(generation);
        connectionChanged();
      } catch (error) {
        if (generation === epoch) void stop("opening_failed",
          {message:error.message === "live_cancelled" ? "Live interrompu." : "Connexion Live impossible. Touche le micro et répète ta phrase."});
      }
    }
    async function arm() {
      if (leaseId || state.capture !== "closed" || state.changing || closePromise || doc.hidden) return false;
      if (state.mode !== "live" || !state.loaded || !state.available || !availableBrowser) return false;
      if (!options.getSoundEnabled?.()) { message("sound_off", "Réactive la voix, puis touche le micro pour parler en Live."); return false; }
      const generation = ++epoch;
      const bearer = options.getToken?.();
      const requestedThread = options.getThread?.();
      state.capture = "requesting";
      state.reason = state.message = "";
      publish();
      callbacks("beforeArm");
      try {
        // Resume audio in the user gesture; acquiring input is deliberately
        // deferred until the server grants this owner's exclusive arm lease.
        context = new AudioConstructor();
        let audioError = null;
        const audioReady = context.resume().catch(error => { audioError = error; });
        const currentContext = context;
        const acquired = await request("/api/live/arm", {client_id:clientId, thread_id:requestedThread}, 5000, bearer);
        if (generation !== epoch) {
          if (acquired.lease_id) void request("/api/live/sessions/close", {client_id:clientId,
            lease_id:acquired.lease_id, reason:"cancelled_before_capture", drain:false, release_arm:true}, 5000, bearer).catch(() => {});
          return false;
        }
        leaseId = acquired.lease_id;
        leaseThread = requestedThread;
        preference(acquired);
        assertCurrent(generation);
        state.lease_state = acquired.lease_state || "armed";
        state.session_state = acquired.session_state || "absent";
        state.capabilities = {...state.capabilities,
          heartbeat_seconds:acquired.heartbeat_seconds || state.capabilities?.heartbeat_seconds,
          lease_seconds:acquired.lease_seconds || state.capabilities?.lease_seconds};
        await connectControl(generation);
        assertCurrent(generation);
        const stream = await nav.mediaDevices.getUserMedia({audio:{channelCount:1,
          echoCancellation:true, noiseSuppression:true, autoGainControl:true}, video:false});
        if (generation !== epoch || doc.hidden) {
          for (const track of stream.getTracks()) track.stop();
          return false;
        }
        media = stream;
        await audioReady;
        if (audioError) throw audioError;
        if (currentContext.state !== "running") throw new Error("L’audio est suspendu. Touche le micro pour reprendre.");
        assertCurrent(generation);
        await currentContext.audioWorklet.addModule("/assets/live-audio-worklet.js");
        assertCurrent(generation);
        destination = currentContext.createMediaStreamDestination();
        worklet = new env.AudioWorkletNode(currentContext, "jade-live-capture", {
          numberOfInputs:1, numberOfOutputs:1, outputChannelCount:[1], channelCount:1,
          channelCountMode:"explicit"});
        source = currentContext.createMediaStreamSource(stream);
        source.connect(worklet);
        worklet.connect(destination);
        worklet.port.onmessage = ({data}) => {
          if (generation !== epoch || state.capture !== "armed") return;
          if (data.type === "speech") void openSession(generation);
          else if (data.type === "speech_activity") speechActive = Boolean(data.active);
          else if (data.type === "sent_speech") {
            // The initial voice may precede both the next periodic heartbeat
            // and its provider transcript. Establish pending input before a
            // rapid mute; this observation never creates/wakes a session.
            if (!sentSpeech) heartbeat(true);
            sentSpeech = true; pendingResponse = true;
          }
          else if (data.type === "overflow") void stop("buffer_overflow",
            {message:"La connexion est trop lente. Touche le micro et répète ta phrase."});
        };
        for (const track of stream.getTracks()) track.onended = () => {
          if (generation === epoch && state.capture === "armed") void stop("microphone_ended",
            {message:"Le microphone s’est arrêté. Touche-le pour reprendre."});
        };
        currentContext.onstatechange = () => {
          if (generation === epoch && state.capture === "armed" && currentContext.state !== "running")
            void stop("audio_suspended", {message:"L’audio a été suspendu. Touche le micro pour reprendre."});
        };
        state.capture = "armed";
        publish();
        return true;
      } catch (error) {
        if (generation === epoch) await stop("arm_failed", {message:error.name === "NotAllowedError" ?
          "Accès au micro refusé. Autorise-le, puis touche le micro." : error.message});
        return false;
      }
    }
    async function stop(reason = "user_stop", config = {}) {
      // Physical capture/output are revoked synchronously, before any fetch.
      const id = leaseId, bearer = options.getToken?.();
      const shouldClose = Boolean(id);
      epoch++;
      releaseAudio();
      closeControl();
      cancelLater(drainTimer); drainTimer = null;
      leaseId = leaseThread = null;
      pendingWake = false; wakeStarted = null;
      state.lease_state = "closed";
      state.session_state = shouldClose ? "closing" : "absent";
      state.reason = reason;
      if (config.message) state.message = config.message;
      publish();
      if (!shouldClose) return closePromise;
      if (closePromise) return closePromise;
      closePromise = (async () => {
        try {
          const result = await request("/api/live/sessions/close", {client_id:clientId, lease_id:id,
            reason, drain:false, release_arm:true}, 5000, bearer);
          state.session_state = result.session_state || result.state?.session_state || "absent";
          if (state.session_state === "closed") state.session_state = "absent";
        } catch (_) {
          state.session_state = "close_unconfirmed";
          if (!config.message) state.message = "Micro coupé. La fermeture distante reste à confirmer.";
        } finally {
          if (["opening_unknown", "close_unconfirmed", "closing"].includes(state.session_state)) {
            state.available = false;
            if (!config.message) state.message = "Micro coupé. Vérifie la fermeture distante depuis Profil avant de reprendre.";
            if (state.session_state === "closing") state.session_state = "close_unconfirmed";
          }
          closePromise = null; publish();
        }
      })();
      return closePromise;
    }
    async function mute() {
      if (state.lease_state === "draining") return stop("mute_again");
      if (!leaseId || !peer || !sentSpeech || opening) return stop("mute");
      const id = leaseId, generation = epoch;
      stopCapture();
      state.lease_state = "draining";
      state.reason = "mute";
      state.message = "Micro coupé. Jade termine sa réponse.";
      publish();
      // Never extended by transcripts, audio or new server activity.
      drainTimer = later(() => {
        if (generation === epoch) void stop("drain_timeout");
      }, 15000);
      try {
        const result = await request("/api/live/sessions/close", {client_id:clientId, lease_id:id,
          reason:"mute", drain:true, release_arm:true}, 5000);
        if (generation === epoch) acceptSnapshot(result.state || result, generation);
      } catch (_) {
        if (generation === epoch) void stop("drain_failed");
      }
    }
    function toggleMicrophone() {
      return state.capture !== "closed" || leaseId ? mute() : arm();
    }
    return {refresh, setMode, arm, mute, stop, toggleMicrophone,
      get state() { return snapshot(); }, get mode() { return state.mode; },
      get active() { return Boolean(leaseId || state.capture !== "closed" || closePromise); }};
  }
  window.JadeLive = {create};
  if (typeof window.dispatchEvent === "function") window.dispatchEvent(new Event("jade-live-ready"));
})();
