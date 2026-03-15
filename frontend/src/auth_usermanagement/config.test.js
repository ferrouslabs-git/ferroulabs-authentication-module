import { describe, expect, it } from "vitest";

import { buildAuthConfig, isSafeInvitePath } from "./config";

function loadModuleWithConfig(env) {
  return {
    AUTH_CONFIG: buildAuthConfig(env),
  };
}

describe("auth module config portability", () => {
  it("uses neutral defaults when env is missing", () => {
    const { AUTH_CONFIG } = loadModuleWithConfig({});

    expect(AUTH_CONFIG.namespace).toBe("authum");
    expect(AUTH_CONFIG.apiBasePath).toBe("/auth");
    expect(AUTH_CONFIG.callbackPath).toBe("/callback");
    expect(AUTH_CONFIG.invitePathPrefix).toBe("/invite/");
  });

  it("normalizes custom env paths and namespace", () => {
    const { AUTH_CONFIG } = loadModuleWithConfig({
      VITE_AUTH_NAMESPACE: "acmeauth",
      VITE_AUTH_API_BASE_PATH: "iam/",
      VITE_AUTH_CALLBACK_PATH: "signin/callback/",
      VITE_AUTH_INVITE_PATH_PREFIX: "join",
    });

    expect(AUTH_CONFIG.namespace).toBe("acmeauth");
    expect(AUTH_CONFIG.apiBasePath).toBe("/iam");
    expect(AUTH_CONFIG.callbackPath).toBe("/signin/callback");
    expect(AUTH_CONFIG.invitePathPrefix).toBe("/join/");
  });

  it("validates invite path token format using configured prefix", () => {
    const cfg = buildAuthConfig({ VITE_AUTH_INVITE_PATH_PREFIX: "/join/" });

    expect(isSafeInvitePath(`${cfg.invitePathPrefix}abcDEF_123`, cfg)).toBe(true);
    expect(isSafeInvitePath(`${cfg.invitePathPrefix}abc-123`, cfg)).toBe(true);
    expect(isSafeInvitePath(`${cfg.invitePathPrefix}bad/token`, cfg)).toBe(false);
    expect(isSafeInvitePath("/invite/abc123", cfg)).toBe(false);
  });
});
