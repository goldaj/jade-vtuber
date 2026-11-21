/* Private Jade WebSocket streaming transport (not OpenAI Realtime).
 * The token is sent inside the authenticated same-origin TLS session, never
 * in a URL, cookies, or browser storage. HTTP/WAV remains a separate fallback.
 */
"use strict";
window.JadeDuplex = (() => {
  function supported() {
    return typeof WebSocket !== "undefined" && location.protocol === "https:";
  }

  function toPcm(samples, sampleRate) {
    const stride = sampleRate / 16000;
    if (!Number.isFinite(stride) || stride < 1 || stride > 16)
      throw new Error("Fréquence micro invalide.");
    const length = Math.floor(samples.length / stride);
    const bytes = new Uint8Array(length * 2);
    const view = new DataView(bytes.buffer);
    for (let i = 0; i < length; i++) {
      const first = Math.floor(i * stride);
      const last = Math.min(samples.length, Math.max(first + 1, Math.floor((i + 1) * stride)));
      let total = 0;
      for (let n = first; n < last; n++) total += samples[n];
      const level = Math.max(-1, Math.min(1, total / (last - first)));
      view.setInt16(i * 2, Math.round(level * 32767), true);
    }
    return bytes;
  }

  function create({token, session, speak, onEvent}) {
    if (!supported()) return null;
    const ws = new WebSocket("wss://" + location.host + "/api/duplex", "jade-v1");
    ws.binaryType = "arraybuffer";
    let ready = false, ending = false, settled = false, queuedBytes = 0;
    const pending = [];
    let sequence = Promise.resolve();
    let succeed, fail;
    const done = new Promise((resolve, reject) => { succeed = resolve; fail = reject; });
    done.catch(() => {}); // A failed handshake can precede the microphone stop.

    function settle(error) {
      if (settled) return;
      settled = true;
      if (error) fail(error);
      else succeed();
    }
    function send(value) {
      if (ws.readyState !== WebSocket.OPEN)
        throw new Error("Connexion vocale interrompue.");
      if (ws.bufferedAmount > 420000)
        throw new Error("Connexion vocale saturée.");
      ws.send(value);
    }
    ws.onopen = () => {
      try { send(JSON.stringify({type:"auth", token, session})); }
      catch (error) { settle(error); ws.close(); }
    };
    ws.onmessage = ({data}) => {
      sequence = sequence.then(async () => {
        if (typeof data !== "string" || data.length > 10000000)
          throw new Error("Réponse vocale invalide.");
        const event = JSON.parse(data);
        if (event.type === "ready") {
          if (ready || settled) return;
          ready = true;
          send(JSON.stringify({type:"start", speak: Boolean(speak)}));
          for (const bytes of pending) send(bytes);
          pending.length = 0;
          queuedBytes = 0;
          if (ending) send(JSON.stringify({type:"end"}));
        } else if (event.type === "error") {
          throw new Error(event.error || "Session vocale indisponible.");
        } else if (event.type === "done") {
          await onEvent(event);
          settle();
          ws.close();
        } else if (event.type === "cancelled") {
          settle(new Error("Conversation interrompue."));
          ws.close();
        } else {
          await onEvent(event);
        }
      }).catch(error => {
        settle(error);
        ws.close();
      });
    };
    ws.onerror = () => settle(new Error("Connexion vocale indisponible."));
    ws.onclose = () => {
      if (!settled) settle(new Error("La connexion vocale s'est terminée."));
    };
    return {
      push(samples, rate) {
        if (ending || settled) return;
        const bytes = toPcm(samples, rate);
        if (!bytes.length) return;
        if (bytes.length > 32768 || queuedBytes + bytes.length > 640000)
          throw new Error("Audio trop long.");
        if (ready) send(bytes);
        else { pending.push(bytes); queuedBytes += bytes.length; }
      },
      async finish() {
        if (!ending) {
          ending = true;
          if (ready) send(JSON.stringify({type:"end"}));
        }
        return done;
      },
      cancel() {
        if (settled) return;
        try {
          if (ready) send(JSON.stringify({type:"cancel"}));
        } catch (_) {}
        settle(new Error("Conversation interrompue."));
        ws.close();
      },
      get ready() { return ready; }
    };
  }

  return {supported, create};
})();
