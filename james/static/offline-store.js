'use strict';

// One device snapshot. A generation protects against late fetches after logout.
((root) => {
  const KEY = 'james-offline-v1';
  const token = () => root.crypto?.randomUUID() || `${Date.now()}-${Math.random()}`;
  function state(storage) {
    try { return JSON.parse(storage.getItem(KEY)) || { generation: 0, owner: null }; }
    catch { return { generation: 0, owner: null }; }
  }
  const api = {
    claim(storage, owner) {
      let value = state(storage);
      if (value.owner !== owner) {
        value = { generation: token(), owner };
        storage.setItem(KEY, JSON.stringify(value));
      }
      return value.generation;
    },
    save(storage, owner, generation, snapshot) {
      const value = state(storage);
      if (value.owner !== owner || value.generation !== generation || snapshot.owner !== owner) return false;
      if (value.snapshot && snapshot.saved_at < value.snapshot.saved_at) return false;
      storage.setItem(KEY, JSON.stringify({ ...value, snapshot }));
      return true;
    },
    read(storage) { return state(storage).snapshot || null; },
    clear(storage, owner) {
      const value = state(storage);
      if (owner && value.owner !== owner) return;
      storage.setItem(KEY, JSON.stringify({ generation: token(), owner: null }));
    },
  };
  if (typeof module !== 'undefined') module.exports = api;
  else root.JamesOffline = api;
})(typeof window === 'undefined' ? {} : window);
