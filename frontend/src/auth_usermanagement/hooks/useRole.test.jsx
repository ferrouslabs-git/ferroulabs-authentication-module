// @vitest-environment jsdom

import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";

// Mock useAuth before importing useRole
const mockAuth = { scopeContext: null, tenantId: null, tenants: [], changeTenant: vi.fn() };
vi.mock("../hooks/useAuth", () => ({ useAuth: () => mockAuth }));
vi.mock("../context/AuthProvider", () => ({
  AuthContext: React.createContext(null),
}));

// Must import after mocks are set up
import { useRole } from "../hooks/useRole";

// useTenant depends on useAuth, so it reads from our mock too

describe("useRole — v3 permission-based checks", () => {
  beforeEach(() => {
    mockAuth.scopeContext = null;
    mockAuth.tenantId = null;
    mockAuth.tenants = [];
  });

  it('can("data:read") returns true when resolved_permissions includes "data:read"', () => {
    mockAuth.scopeContext = { resolved_permissions: ["data:read", "data:write"] };
    const { result } = renderHook(() => useRole());
    expect(result.current.can("data:read")).toBe(true);
  });

  it('can("account:delete") returns false when permission is absent', () => {
    mockAuth.scopeContext = { resolved_permissions: ["data:read"] };
    const { result } = renderHook(() => useRole());
    expect(result.current.can("account:delete")).toBe(false);
  });

  it('isOwner is true only when "account:delete" is in permissions', () => {
    mockAuth.scopeContext = {
      resolved_permissions: ["account:delete", "account:read", "members:manage"],
    };
    const { result } = renderHook(() => useRole());
    expect(result.current.isOwner).toBe(true);
  });

  it('isOwner is false when "account:delete" is absent', () => {
    mockAuth.scopeContext = { resolved_permissions: ["account:read", "members:manage"] };
    const { result } = renderHook(() => useRole());
    expect(result.current.isOwner).toBe(false);
  });

  it('isAdminOrOwner is true when "members:manage" is in permissions', () => {
    mockAuth.scopeContext = { resolved_permissions: ["members:manage"] };
    const { result } = renderHook(() => useRole());
    expect(result.current.isAdminOrOwner).toBe(true);
  });

  it("empty permissions array → all checks return false", () => {
    mockAuth.scopeContext = { resolved_permissions: [] };
    const { result } = renderHook(() => useRole());
    expect(result.current.can("data:read")).toBe(false);
    expect(result.current.can("account:delete")).toBe(false);
    expect(result.current.isOwner).toBe(false);
    expect(result.current.isAdminOrOwner).toBe(false);
  });

  it("falls back to legacy role-level checks when no scopeContext", () => {
    mockAuth.scopeContext = null;
    mockAuth.tenants = [{ id: "t1", role: "admin" }];
    mockAuth.tenantId = "t1";
    const { result } = renderHook(() => useRole());
    // Legacy: admin can do "member" level
    expect(result.current.can("member")).toBe(true);
    expect(result.current.can("owner")).toBe(false);
  });
});
