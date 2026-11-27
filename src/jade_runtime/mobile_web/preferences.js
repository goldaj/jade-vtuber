/* Device-local presentation settings only. Authentication, conversations,
 * account identities and media/session state never belong in this store. */
"use strict";
(() => {
  const STORAGE_KEY = "jade.mobile.preferences.v1";
  const validators = Object.freeze({
    soundEnabled: value => typeof value === "boolean",
    notificationsEnabled: value => typeof value === "boolean",
    portraitMotionEnabled: value => typeof value === "boolean",
    avatarShakeEnabled: value => typeof value === "boolean",
    room: value => ["bedroom", "kitchen"].includes(value),
    avatarModel: value => ["classic", "next"].includes(value),
    deploymentLevel: value => ["all", "warning", "error"].includes(value)
  });
  const valid = (key, value) => Object.prototype.hasOwnProperty.call(validators, key) && validators[key](value);

  function read() {
    try {
      const raw = window.localStorage?.getItem(STORAGE_KEY);
      if (!raw || raw.length > 4096) return {};
      const record = JSON.parse(raw);
      if (record?.version !== 1 || !record.values || typeof record.values !== "object" || Array.isArray(record.values))
        return {};
      return Object.fromEntries(Object.entries(record.values).filter(([key, value]) => valid(key, value)));
    } catch (_) {
      // Disabled/private browser storage or a damaged record must not block Jade.
      return {};
    }
  }

  let values = read();
  window.JadePreferences = Object.freeze({
    get(key, fallback) {
      return valid(key, values[key]) ? values[key] : fallback;
    },
    set(key, value) {
      if (!valid(key, value)) return false;
      // Merge with the last stored settings so another tab's unrelated choice
      // survives. Keep this session usable even when writing is unavailable.
      values = {...values, ...read(), [key]:value};
      try {
        if (!window.localStorage) return false;
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify({version:1, values}));
        return true;
      } catch (_) {
        return false;
      }
    }
  });
})();
