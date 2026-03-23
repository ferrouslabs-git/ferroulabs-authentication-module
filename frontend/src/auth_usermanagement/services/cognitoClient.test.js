// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from "vitest";

// Stub import.meta.env values BEFORE importing the module under test
vi.stubEnv("VITE_COGNITO_DOMAIN", "https://mypool.auth.eu-west-1.amazoncognito.com");
vi.stubEnv("VITE_COGNITO_CLIENT_ID", "test-client-id");
vi.stubEnv("VITE_COGNITO_REDIRECT_URI", "http://localhost:5173/callback");

// We need to dynamically import because cognitoClient reads env at module level
let cognitoClient;

beforeEach(async () => {
  vi.restoreAllMocks();
  sessionStorage.clear();
  // Re-import fresh copy so env stubs take effect
  cognitoClient = await import("./cognitoClient.js");
});

describe("PKCE code generation", () => {
  it("getHostedLoginUrl stores PKCE verifier in sessionStorage", async () => {
    // Provide crypto.subtle.digest stub
    const url = await cognitoClient.getHostedLoginUrl();

    expect(url).toContain("https://mypool.auth.eu-west-1.amazoncognito.com/oauth2/authorize");
    expect(url).toContain("client_id=test-client-id");
    expect(url).toContain("code_challenge_method=S256");
    expect(url).toContain("code_challenge=");

    const storedVerifier = sessionStorage.getItem("authum_pkce_code_verifier");
    expect(storedVerifier).toBeTruthy();
    expect(storedVerifier.length).toBe(64);
  });

  it("getHostedSignupUrl uses /signup endpoint", async () => {
    const url = await cognitoClient.getHostedSignupUrl();
    expect(url).toContain("/signup?");
    expect(url).toContain("client_id=test-client-id");
  });
});

describe("exchangeAuthCodeForTokens", () => {
  it("sends code and PKCE verifier to Cognito token endpoint", async () => {
    // Seed a PKCE verifier
    sessionStorage.setItem("authum_pkce_code_verifier", "test-verifier-abc");

    const mockResponse = {
      access_token: "at-123",
      id_token: "it-456",
      refresh_token: "rt-789",
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    const result = await cognitoClient.exchangeAuthCodeForTokens("auth-code-xyz");

    expect(result.access_token).toBe("at-123");
    expect(result.refresh_token).toBe("rt-789");

    // Verify fetch was called correctly
    const [url, opts] = globalThis.fetch.mock.calls[0];
    expect(url).toBe("https://mypool.auth.eu-west-1.amazoncognito.com/oauth2/token");
    expect(opts.method).toBe("POST");
    expect(opts.body).toContain("grant_type=authorization_code");
    expect(opts.body).toContain("code=auth-code-xyz");
    expect(opts.body).toContain("code_verifier=test-verifier-abc");

    // Verifier should be cleared after successful exchange
    expect(sessionStorage.getItem("authum_pkce_code_verifier")).toBeNull();
  });

  it("throws on error response from Cognito", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ error: "invalid_grant", error_description: "Code expired" }),
    });

    await expect(cognitoClient.exchangeAuthCodeForTokens("bad-code")).rejects.toThrow("Code expired");
  });
});

describe("decodeJwt", () => {
  it("decodes a valid JWT payload", () => {
    // Create a minimal JWT: header.payload.signature
    const header = btoa(JSON.stringify({ alg: "RS256" }));
    const payload = btoa(JSON.stringify({ sub: "user-1", email: "a@b.com", exp: 9999999999 }));
    const fakeJwt = `${header}.${payload}.fake-signature`;

    const decoded = cognitoClient.decodeJwt(fakeJwt);
    expect(decoded.sub).toBe("user-1");
    expect(decoded.email).toBe("a@b.com");
    expect(decoded.exp).toBe(9999999999);
  });

  it("returns null for invalid JWT", () => {
    expect(cognitoClient.decodeJwt("not-a-jwt")).toBeNull();
  });
});

describe("refreshTokens (deprecated)", () => {
  it("sends refresh_token grant to Cognito", async () => {
    const mockResponse = { access_token: "new-at", id_token: "new-it" };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    const result = await cognitoClient.refreshTokens("rt-old");

    expect(result.access_token).toBe("new-at");
    const [, opts] = globalThis.fetch.mock.calls[0];
    expect(opts.body).toContain("grant_type=refresh_token");
    expect(opts.body).toContain("refresh_token=rt-old");
  });
});
