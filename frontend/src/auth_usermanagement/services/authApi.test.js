// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from "vitest";

// Use vi.hoisted so the mock object is available when vi.mock runs (hoisted)
const mockAxiosInstance = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
}));

vi.mock("axios", () => ({
  default: {
    create: () => mockAxiosInstance,
  },
}));

// Now import the module under test
import {
  syncUser,
  getCurrentUser,
  listMyTenants,
  refreshAccessToken,
  storeRefreshCookie,
  clearRefreshCookie,
  inviteTenantUser,
  acceptInvitation,
  getInvitationDetails,
  suspendUser,
  unsuspendUser,
} from "./authApi.js";

beforeEach(() => {
  mockAxiosInstance.get.mockReset();
  mockAxiosInstance.post.mockReset();
  mockAxiosInstance.patch.mockReset();
  mockAxiosInstance.delete.mockReset();
  // Expire any cookies set by previous tests
  document.cookie.split(";").forEach((c) => {
    const name = c.split("=")[0].trim();
    if (name) document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
  });
});

describe("authApi – auth headers", () => {
  it("syncUser sends Bearer token", async () => {
    mockAxiosInstance.post.mockResolvedValue({ data: { id: "u1" } });
    await syncUser("tok-abc");
    const call = mockAxiosInstance.post.mock.calls[0];
    expect(call[0]).toBe("/sync");
    expect(call[2].headers.Authorization).toBe("Bearer tok-abc");
  });

  it("getCurrentUser sends GET /me with Bearer", async () => {
    mockAxiosInstance.get.mockResolvedValue({ data: { email: "a@b.com" } });
    const user = await getCurrentUser("tok-1");
    expect(user.email).toBe("a@b.com");
    expect(mockAxiosInstance.get.mock.calls[0][1].headers.Authorization).toBe("Bearer tok-1");
  });

  it("listMyTenants sends GET /tenants/my", async () => {
    mockAxiosInstance.get.mockResolvedValue({ data: [{ id: "t1", name: "Acme" }] });
    const tenants = await listMyTenants("tok-2");
    expect(tenants).toHaveLength(1);
    expect(tenants[0].name).toBe("Acme");
  });
});

describe("authApi – invitation endpoints", () => {
  it("inviteTenantUser posts to /invite with scope headers", async () => {
    mockAxiosInstance.post.mockResolvedValue({ data: { invitation_id: "inv-1" } });
    await inviteTenantUser("tok", "tenant-1", "a@b.com", "member", {
      scopeType: "account",
      scopeId: "tenant-1",
      targetRoleName: "account_member",
    });
    const [path, body, opts] = mockAxiosInstance.post.mock.calls[0];
    expect(path).toBe("/invite");
    expect(body.email).toBe("a@b.com");
    expect(body.target_role_name).toBe("account_member");
    expect(opts.headers["X-Tenant-ID"]).toBe("tenant-1");
    expect(opts.headers["X-Scope-Type"]).toBe("account");
  });

  it("getInvitationDetails sends GET /invites/:token", async () => {
    mockAxiosInstance.get.mockResolvedValue({ data: { email: "x@y.com", tenant_name: "Test" } });
    const data = await getInvitationDetails("abc-token");
    expect(mockAxiosInstance.get.mock.calls[0][0]).toBe("/invites/abc-token");
    expect(data.tenant_name).toBe("Test");
  });

  it("acceptInvitation posts to /invites/accept with auth", async () => {
    mockAxiosInstance.post.mockResolvedValue({ data: { message: "ok" } });
    await acceptInvitation("auth-tok", "invite-tok");
    const [path, body, opts] = mockAxiosInstance.post.mock.calls[0];
    expect(path).toBe("/invites/accept");
    expect(body.token).toBe("invite-tok");
    expect(opts.headers.Authorization).toBe("Bearer auth-tok");
  });
});

describe("authApi – refresh / cookie", () => {
  it("refreshAccessToken sends CSRF token from cookie", async () => {
    // Set a readable CSRF cookie
    document.cookie = "authum_csrf_token=csrf-value-123; path=/";

    mockAxiosInstance.post.mockResolvedValue({
      data: { access_token: "new-at", id_token: "new-it", expires_in: 3600 },
    });

    const result = await refreshAccessToken();
    expect(result.access_token).toBe("new-at");

    const [path, , opts] = mockAxiosInstance.post.mock.calls[0];
    expect(path).toBe("/token/refresh");
    expect(opts.headers["X-CSRF-Token"]).toBe("csrf-value-123");
    expect(opts.headers["X-Requested-With"]).toBe("XMLHttpRequest");
  });

  it("refreshAccessToken works without CSRF cookie", async () => {
    mockAxiosInstance.post.mockResolvedValue({
      data: { access_token: "at-2" },
    });

    const result = await refreshAccessToken();
    expect(result.access_token).toBe("at-2");
    // No X-CSRF-Token header when cookie is absent
    const headers = mockAxiosInstance.post.mock.calls[0][2].headers;
    expect(headers["X-CSRF-Token"]).toBeUndefined();
  });

  it("storeRefreshCookie posts to /cookie/store-refresh", async () => {
    mockAxiosInstance.post.mockResolvedValue({ data: { stored: true } });
    await storeRefreshCookie("tok", "rt-value");
    const [path, body] = mockAxiosInstance.post.mock.calls[0];
    expect(path).toBe("/cookie/store-refresh");
    expect(body.refresh_token).toBe("rt-value");
  });

  it("clearRefreshCookie posts to /cookie/clear-refresh", async () => {
    mockAxiosInstance.post.mockResolvedValue({ data: {} });
    await clearRefreshCookie();
    expect(mockAxiosInstance.post.mock.calls[0][0]).toBe("/cookie/clear-refresh");
  });
});

describe("authApi – user suspension", () => {
  it("suspendUser sends PATCH to correct path", async () => {
    mockAxiosInstance.patch.mockResolvedValue({ data: { is_active: false } });
    const result = await suspendUser("tok", "t1", "u1");
    expect(result.is_active).toBe(false);
    expect(mockAxiosInstance.patch.mock.calls[0][0]).toBe("/users/u1/suspend");
  });

  it("unsuspendUser sends PATCH to correct path", async () => {
    mockAxiosInstance.patch.mockResolvedValue({ data: { is_active: true } });
    const result = await unsuspendUser("tok", "t1", "u1");
    expect(result.is_active).toBe(true);
    expect(mockAxiosInstance.patch.mock.calls[0][0]).toBe("/users/u1/unsuspend");
  });
});
