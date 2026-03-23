// @vitest-environment jsdom

import React from "react";
import { describe, expect, it } from "vitest";
import { renderHook } from "@testing-library/react";
import { AuthContext } from "../context/AuthProvider";
import { useAuth } from "./useAuth";

function wrapper({ children }) {
  const value = {
    token: "test-token",
    user: { email: "a@b.com" },
    tenants: [],
    tenantId: null,
    isLoading: false,
    authError: "",
    isAuthenticated: true,
    loginWithToken: () => {},
    logout: () => {},
    changeTenant: () => {},
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

describe("useAuth", () => {
  it("returns context values when inside AuthProvider", () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    expect(result.current.token).toBe("test-token");
    expect(result.current.user.email).toBe("a@b.com");
    expect(result.current.isAuthenticated).toBe(true);
  });

  it("throws when used outside AuthProvider", () => {
    expect(() => {
      renderHook(() => useAuth());
    }).toThrow("useAuth must be used within AuthProvider");
  });
});
