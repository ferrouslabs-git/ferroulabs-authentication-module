import axios from "axios";
import { AUTH_CONFIG } from "../config";

const api = axios.create({
  baseURL: AUTH_CONFIG.apiBasePath,
  timeout: 15000,
});

function authHeaders(token, tenantId, { scopeType, scopeId } = {}) {
  const headers = { Authorization: `Bearer ${token}` };
  if (scopeType && scopeId) {
    headers["X-Scope-Type"] = scopeType;
    headers["X-Scope-ID"] = scopeId;
  }
  if (tenantId) {
    headers["X-Tenant-ID"] = tenantId;
  }
  return headers;
}

export async function syncUser(token) {
  const res = await api.post("/sync", null, { headers: authHeaders(token) });
  return res.data;
}

export async function getCurrentUser(token) {
  const res = await api.get("/me", { headers: authHeaders(token) });
  return res.data;
}

export async function listMyTenants(token) {
  const res = await api.get("/tenants/my", { headers: authHeaders(token) });
  return res.data;
}

export async function getTenantUsers(token, tenantId) {
  const res = await api.get(`/tenants/${tenantId}/users`, {
    headers: authHeaders(token, tenantId),
  });
  return res.data;
}

export async function getPlatformUsers(token) {
  const res = await api.get('/platform/users', {
    headers: authHeaders(token),
  });
  return res.data;
}

export async function promotePlatformUser(token, userId) {
  const res = await api.patch(`/platform/users/${userId}/promote`, null, {
    headers: authHeaders(token),
  });
  return res.data;
}

export async function demotePlatformUser(token, userId) {
  const res = await api.patch(`/platform/users/${userId}/demote`, null, {
    headers: authHeaders(token),
  });
  return res.data;
}

export async function getPlatformTenants(token) {
  const res = await api.get('/platform/tenants', {
    headers: authHeaders(token),
  });
  return res.data;
}

export async function updateTenantUserRole(token, tenantId, userId, role) {
  const res = await api.patch(
    `/tenants/${tenantId}/users/${userId}/role`,
    { role },
    { headers: authHeaders(token, tenantId) },
  );
  return res.data;
}

export async function removeTenantUser(token, tenantId, userId) {
  const res = await api.delete(`/tenants/${tenantId}/users/${userId}`, {
    headers: authHeaders(token, tenantId),
  });
  return res.data;
}

export async function inviteTenantUser(token, tenantId, email, role, { scopeType, scopeId, targetRoleName } = {}) {
  const body = { email, role };
  if (targetRoleName) body.target_role_name = targetRoleName;
  if (scopeType) body.target_scope_type = scopeType;
  if (scopeId) body.target_scope_id = scopeId;
  const res = await api.post(
    "/invite",
    body,
    { headers: authHeaders(token, tenantId, { scopeType: scopeType || "account", scopeId: scopeId || tenantId }) },
  );
  return res.data;
}

export async function registerSession(token, refreshToken, metadata = {}) {
  const res = await api.post(
    "/sessions/register",
    { refresh_token: refreshToken, ...metadata },
    { headers: authHeaders(token) },
  );
  return res.data; // { session_id, user_id, message }
}

export async function rotateSession(token, sessionId, oldRefreshToken, newRefreshToken, metadata = {}) {
  const res = await api.post(
    `/sessions/${sessionId}/rotate`,
    { old_refresh_token: oldRefreshToken, new_refresh_token: newRefreshToken, ...metadata },
    { headers: authHeaders(token) },
  );
  return res.data; // { session_id, user_id, message }
}

export async function revokeAllSessions(token, currentSessionId) {
  const headers = authHeaders(token);
  if (currentSessionId) {
    headers["X-Current-Session-ID"] = currentSessionId;
  }
  const res = await api.delete("/sessions/all", { headers });
  return res.data;
}

export async function listSessions(token, currentSessionId = null, includeRevoked = false) {
  const headers = authHeaders(token);
  if (currentSessionId) {
    headers["X-Current-Session-ID"] = currentSessionId;
  }
  const res = await api.get("/sessions", {
    headers,
    params: { include_revoked: includeRevoked },
  });
  return res.data;
}

export async function revokeSession(token, sessionId) {
  const res = await api.delete(`/sessions/${sessionId}`, {
    headers: authHeaders(token),
  });
  return res.data;
}

export async function storeRefreshCookie(token, refreshToken) {
  const res = await api.post(
    "/cookie/store-refresh",
    { refresh_token: refreshToken },
    { headers: authHeaders(token) },
  );
  return res.data;
}

function _getCookie(name) {
  const match = document.cookie.split("; ").find((c) => c.startsWith(name + "="));
  return match ? decodeURIComponent(match.split("=")[1]) : null;
}

/**
 * Exchange the HttpOnly refresh cookie for new tokens via the backend proxy.
 * No body needed — the browser sends the HttpOnly cookie automatically.
 * Sends the CSRF token (read from the readable csrf cookie) as X-CSRF-Token header.
 */
export async function refreshAccessToken() {
  const csrfToken = _getCookie(AUTH_CONFIG.csrfCookieName);
  const res = await api.post(
    "/token/refresh",
    null,
    {
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        ...(csrfToken && { "X-CSRF-Token": csrfToken }),
      },
    },
  );
  return res.data; // { access_token, id_token, expires_in }
}

export async function clearRefreshCookie() {
  const res = await api.post("/cookie/clear-refresh");
  return res.data;
}

export async function suspendUser(token, tenantId, userId) {
  const res = await api.patch(`/users/${userId}/suspend`, null, {
    headers: authHeaders(token, tenantId),
  });
  return res.data;
}

export async function unsuspendUser(token, tenantId, userId) {
  const res = await api.patch(`/users/${userId}/unsuspend`, null, {
    headers: authHeaders(token, tenantId),
  });
  return res.data;
}

export async function getInvitationDetails(token) {
  const res = await api.get(`/invites/${token}`);
  return res.data;
}

export async function acceptInvitation(authToken, inviteToken) {
  const res = await api.post(
    "/invites/accept",
    { token: inviteToken },
    { headers: authHeaders(authToken) }
  );
  return res.data;
}

// ── v3.0 scope-aware endpoints ──────────────────────────────────

export async function getRoleDefinitions(token) {
  const res = await api.get("/config/roles", { headers: authHeaders(token) });
  return res.data;
}

export async function listMySpaces(token) {
  const res = await api.get("/spaces/my", { headers: authHeaders(token) });
  return res.data;
}

export async function getAccountSpaces(token, accountId) {
  const res = await api.get(`/accounts/${accountId}/spaces`, {
    headers: authHeaders(token, accountId, { scopeType: "account", scopeId: accountId }),
  });
  return res.data;
}

export async function inviteToSpace(token, spaceId, data, tenantId) {
  const res = await api.post(
    `/spaces/${spaceId}/invite`,
    data,
    { headers: authHeaders(token, tenantId, { scopeType: "space", scopeId: spaceId }) },
  );
  return res.data;
}

export async function getAccountMembers(token, accountId) {
  const res = await api.get(`/tenants/${accountId}/users`, {
    headers: authHeaders(token, accountId, { scopeType: "account", scopeId: accountId }),
  });
  return res.data;
}

export async function createTenant(token, tenantName, plan = "free") {
  const res = await api.post(
    "/tenants",
    { name: tenantName, plan },
    { headers: authHeaders(token) }
  );
  return res.data;
}

export async function suspendPlatformTenant(token, tenantId) {
  const res = await api.patch(`/platform/tenants/${tenantId}/suspend`, null, {
    headers: authHeaders(token),
  });
  return res.data;
}

export async function unsuspendPlatformTenant(token, tenantId) {
  const res = await api.patch(`/platform/tenants/${tenantId}/unsuspend`, null, {
    headers: authHeaders(token),
  });
  return res.data;
}
