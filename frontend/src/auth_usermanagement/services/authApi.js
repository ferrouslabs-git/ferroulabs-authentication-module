import axios from "axios";

const api = axios.create({
  baseURL: "/auth",
  timeout: 15000,
});

function authHeaders(token, tenantId) {
  const headers = { Authorization: `Bearer ${token}` };
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

export async function inviteTenantUser(token, tenantId, email, role) {
  const res = await api.post(
    "/invite",
    { email, role },
    { headers: authHeaders(token, tenantId) },
  );
  return res.data;
}

export async function revokeAllSessions(token, currentSessionId) {
  const headers = authHeaders(token);
  if (currentSessionId) {
    headers["X-Current-Session-ID"] = currentSessionId;
  }
  const res = await api.delete("/sessions/all", { headers });
  return res.data;
}

export async function suspendUser(token, userId) {
  const res = await api.patch(`/users/${userId}/suspend`, null, {
    headers: authHeaders(token),
  });
  return res.data;
}

export async function unsuspendUser(token, userId) {
  const res = await api.patch(`/users/${userId}/unsuspend`, null, {
    headers: authHeaders(token),
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
