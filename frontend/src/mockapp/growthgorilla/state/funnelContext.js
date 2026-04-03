const STORAGE_KEY = "gg_funnel_context_v1";

function isBrowser() {
  return typeof window !== "undefined";
}

export function getFunnelContext() {
  if (!isBrowser()) return null;
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (_error) {
    return null;
  }
}

export function setFunnelContext(nextContext) {
  if (!isBrowser()) return;
  window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(nextContext));
}

export function mergeFunnelContext(patch) {
  const current = getFunnelContext() || {};
  const merged = {
    ...current,
    ...patch,
    capturedAt: current.capturedAt || new Date().toISOString(),
  };
  setFunnelContext(merged);
  return merged;
}

export function clearFunnelContext() {
  if (!isBrowser()) return;
  window.sessionStorage.removeItem(STORAGE_KEY);
}
