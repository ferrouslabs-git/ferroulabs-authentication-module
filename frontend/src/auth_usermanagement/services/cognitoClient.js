import { AUTH_CONFIG, STORAGE_KEYS, isBrowser } from "../config";

const cognitoDomain = import.meta.env.VITE_COGNITO_DOMAIN;
const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID;

function getRedirectUri() {
  if (import.meta.env.VITE_COGNITO_REDIRECT_URI) {
    return import.meta.env.VITE_COGNITO_REDIRECT_URI;
  }
  if (!isBrowser) {
    return AUTH_CONFIG.callbackPath;
  }
  return `${window.location.origin}${AUTH_CONFIG.callbackPath}`;
}

function toBase64Url(bytes) {
  const binary = String.fromCharCode(...bytes);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function assertAuthConfig() {
  if (!cognitoDomain) {
    throw new Error("Missing VITE_COGNITO_DOMAIN in frontend environment");
  }
  if (!clientId) {
    throw new Error("Missing VITE_COGNITO_CLIENT_ID in frontend environment");
  }
}

function generateCodeVerifier(length = 64) {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~";
  let verifier = "";
  const random = new Uint8Array(length);
  window.crypto.getRandomValues(random);
  for (let i = 0; i < length; i += 1) {
    verifier += chars[random[i] % chars.length];
  }
  return verifier;
}

async function generateCodeChallenge(codeVerifier) {
  const data = new TextEncoder().encode(codeVerifier);
  const digest = await window.crypto.subtle.digest("SHA-256", data);
  return toBase64Url(new Uint8Array(digest));
}

export async function getHostedLoginUrl() {
  assertAuthConfig();

  const codeVerifier = generateCodeVerifier();
  const codeChallenge = await generateCodeChallenge(codeVerifier);
  sessionStorage.setItem(STORAGE_KEYS.pkceCodeVerifier, codeVerifier);

  const redirectUri = getRedirectUri();
  const params = new URLSearchParams({
    client_id: clientId,
    response_type: "code",
    redirect_uri: redirectUri,
    scope: "email openid",
    code_challenge_method: "S256",
    code_challenge: codeChallenge,
  });

  return `${cognitoDomain}/oauth2/authorize?${params.toString()}`;
}

export async function openHostedLogin() {
  const url = await getHostedLoginUrl();
  window.location.href = url;
}

export async function getHostedSignupUrl() {
  assertAuthConfig();

  const codeVerifier = generateCodeVerifier();
  const codeChallenge = await generateCodeChallenge(codeVerifier);
  sessionStorage.setItem(STORAGE_KEYS.pkceCodeVerifier, codeVerifier);

  const redirectUri = getRedirectUri();
  const params = new URLSearchParams({
    client_id: clientId,
    response_type: "code",
    redirect_uri: redirectUri,
    scope: "email openid",
    code_challenge_method: "S256",
    code_challenge: codeChallenge,
  });

  return `${cognitoDomain}/signup?${params.toString()}`;
}

export async function openHostedSignup() {
  const url = await getHostedSignupUrl();
  window.location.href = url;
}

export function getCodeFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get("code");
}

export function clearCodeFromUrl() {
  const url = new URL(window.location.href);
  url.searchParams.delete("code");
  url.searchParams.delete("error");
  url.searchParams.delete("error_description");
  // Reset to home page if on callback route
  if (url.pathname === AUTH_CONFIG.callbackPath) {
    url.pathname = '/';
  }
  window.history.replaceState({}, "", url.toString());
}

export function getAuthErrorFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const error = params.get("error");
  const description = params.get("error_description");
  if (!error) {
    return null;
  }
  return { error, description };
}

export async function exchangeAuthCodeForTokens(code) {
  assertAuthConfig();

  const codeVerifier = sessionStorage.getItem(STORAGE_KEYS.pkceCodeVerifier);
  const redirectUri = getRedirectUri();
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: clientId,
    code,
    redirect_uri: redirectUri,
  });

  if (codeVerifier) {
    body.append("code_verifier", codeVerifier);
  }

  const response = await fetch(`${cognitoDomain}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });

  const result = await response.json();
  if (!response.ok) {
    throw new Error(result.error_description || result.error || "Token exchange failed");
  }

  sessionStorage.removeItem(STORAGE_KEYS.pkceCodeVerifier);
  return result;
}

/**
 * @deprecated Use refreshAccessToken() from authApi.js instead.
 * That function proxies the refresh through the backend, which reads
 * the HttpOnly cookie — keeping the refresh token out of JS memory.
 */
export async function refreshTokens(refreshToken) {
  assertAuthConfig();

  const body = new URLSearchParams({
    grant_type: "refresh_token",
    client_id: clientId,
    refresh_token: refreshToken,
  });

  const response = await fetch(`${cognitoDomain}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });

  const result = await response.json();
  if (!response.ok) {
    throw new Error(result.error_description || result.error || "Token refresh failed");
  }

  return result;
}

export function decodeJwt(token) {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch (error) {
    console.error('Failed to decode JWT:', error);
    return null;
  }
}

export function logoutFromCognito() {
  assertAuthConfig();

  const redirectUri = getRedirectUri();
  // Cognito matches sign-out URLs strictly, so keep a stable trailing slash.
  const logoutRedirectUri = redirectUri.replace(AUTH_CONFIG.callbackPath, '/');
  console.info("[auth] Redirecting to Cognito logout", {
    cognitoDomain,
    clientId,
    logoutRedirectUri,
  });
  const logoutUrl = `${cognitoDomain}/logout?client_id=${clientId}&logout_uri=${encodeURIComponent(logoutRedirectUri)}`;
  window.location.href = logoutUrl;
}
