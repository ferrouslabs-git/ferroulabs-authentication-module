function normalizePathPrefix(path, fallback) {
  const value = (path || fallback || "").trim();
  if (!value) {
    return fallback;
  }
  const withLeading = value.startsWith("/") ? value : `/${value}`;
  return withLeading.replace(/\/+$/, "") || fallback;
}

function normalizeInvitePrefix(path, fallback) {
  const base = normalizePathPrefix(path, fallback.replace(/\/$/, ""));
  return `${base}/`;
}

export const isBrowser = typeof window !== "undefined";

export function buildAuthConfig(env = import.meta.env) {
  const namespace = (env.VITE_AUTH_NAMESPACE || "authum").trim() || "authum";
  return {
    namespace,
    apiBasePath: normalizePathPrefix(env.VITE_AUTH_API_BASE_PATH, "/auth"),
    callbackPath: normalizePathPrefix(env.VITE_AUTH_CALLBACK_PATH, "/callback"),
    invitePathPrefix: normalizeInvitePrefix(env.VITE_AUTH_INVITE_PATH_PREFIX, "/invite/"),
    csrfCookieName: (env.VITE_AUTH_CSRF_COOKIE_NAME || "").trim() || `${namespace}_csrf_token`,
  };
}

export const AUTH_CONFIG = buildAuthConfig();

export function getStorageKey(suffix) {
  return `${AUTH_CONFIG.namespace}_${suffix}`;
}

export const STORAGE_KEYS = {
  tenantId: getStorageKey("tenant_id"),
  postLoginRedirect: getStorageKey("post_login_redirect"),
  pkceCodeVerifier: getStorageKey("pkce_code_verifier"),
};

export const LEGACY_STORAGE_KEYS = {
  tenantId: "trustos_tenant_id",
  postLoginRedirect: "trustos_post_login_redirect",
  accessToken: "trustos_access_token",
  idToken: "trustos_id_token",
  refreshToken: "trustos_refresh_token",
  pkceCodeVerifier: "trustos_pkce_code_verifier",
};

export function isSafeInvitePath(path, config = AUTH_CONFIG) {
  if (typeof path !== "string") {
    return false;
  }
  if (!path.startsWith(config.invitePathPrefix)) {
    return false;
  }
  const token = path.slice(config.invitePathPrefix.length);
  return /^[A-Za-z0-9_-]+$/.test(token);
}
