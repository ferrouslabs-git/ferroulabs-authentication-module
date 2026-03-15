import { createContext, useEffect, useMemo, useState, useRef } from "react";
import { getCurrentUser, listMyTenants, registerSession, rotateSession, revokeAllSessions, storeRefreshCookie, refreshAccessToken, clearRefreshCookie, syncUser } from "../services/authApi";
import {
  clearCodeFromUrl,
  exchangeAuthCodeForTokens,
  getAuthErrorFromUrl,
  getCodeFromUrl,
  logoutFromCognito,
  decodeJwt,
} from "../services/cognitoClient";
import { LEGACY_STORAGE_KEYS, STORAGE_KEYS, isBrowser, isSafeInvitePath } from "../config";

export const AuthContext = createContext(null);

const TENANT_KEY = STORAGE_KEYS.tenantId;
const POST_LOGIN_REDIRECT_KEY = STORAGE_KEYS.postLoginRedirect;
const REFRESH_BEFORE_EXPIRY_MS = 5 * 60 * 1000; // 5 minutes
const CHECK_INTERVAL_MS = 60 * 1000; // Check every minute

function readStorage(key) {
  if (!isBrowser) {
    return null;
  }
  return window.localStorage.getItem(key);
}

function writeStorage(key, value) {
  if (!isBrowser) {
    return;
  }
  window.localStorage.setItem(key, value);
}

function removeStorage(key) {
  if (!isBrowser) {
    return;
  }
  window.localStorage.removeItem(key);
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(
    null,
  );
  const [idToken, setIdToken] = useState(null);
  const [user, setUser] = useState(null);
  const [tenants, setTenants] = useState([]);
  const [tenantId, setTenantId] = useState(
    readStorage(TENANT_KEY) || readStorage(LEGACY_STORAGE_KEYS.tenantId),
  );
  const [isLoading, setIsLoading] = useState(true);
  const [authError, setAuthError] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const refreshTimerRef = useRef(null);
  const skipNextBootstrapRefreshRef = useRef(false);

  // Migrate legacy key names once and clear stale legacy token keys.
  useEffect(() => {
    const legacyTenant = readStorage(LEGACY_STORAGE_KEYS.tenantId);
    if (!readStorage(TENANT_KEY) && legacyTenant) {
      writeStorage(TENANT_KEY, legacyTenant);
    }
    removeStorage(LEGACY_STORAGE_KEYS.tenantId);
    removeStorage(LEGACY_STORAGE_KEYS.accessToken);
    removeStorage(LEGACY_STORAGE_KEYS.idToken);
    removeStorage(LEGACY_STORAGE_KEYS.refreshToken);
  }, []);

  useEffect(() => {
    async function bootstrap() {
      const oauthError = getAuthErrorFromUrl();
      if (oauthError) {
        setAuthError(oauthError.description || oauthError.error || "Authentication failed");
        clearCodeFromUrl();
      }

      if (!token) {
        const authCode = getCodeFromUrl();
        if (authCode) {
          clearCodeFromUrl(); // Clear immediately to prevent re-use on re-render
          try {
            setIsLoading(true);
            const tokens = await exchangeAuthCodeForTokens(authCode);
            if (!tokens.access_token) {
              throw new Error("Cognito token response missing access_token");
            }

            setToken(tokens.access_token);
            if (tokens.id_token) {
              setIdToken(tokens.id_token);
            }
            // Hand off refresh token to HttpOnly cookie — removes it from JS-accessible memory.
            if (tokens.refresh_token) {
              try {
                await storeRefreshCookie(tokens.access_token, tokens.refresh_token);
              } catch (_cookieError) {
                // Best-effort; auth flow continues even if cookie store fails.
              }
            }
            try {
              const sessionData = await registerSession(
                tokens.access_token,
                tokens.refresh_token,
                { user_agent: navigator.userAgent },
              );
              setSessionId(sessionData.session_id);
            } catch (_sessionError) {
              // Session registration is best-effort; auth flow continues without it.
            }
            setAuthError("");
          } catch (error) {
            setAuthError(error?.message || "Unable to exchange auth code");
            setIsLoading(false);
          }
          return;
        }
      }

      if (!token) {
        // No in-memory token and no auth code — attempt silent refresh via HttpOnly cookie.
        if (skipNextBootstrapRefreshRef.current) {
          skipNextBootstrapRefreshRef.current = false;
          setIsLoading(false);
          return;
        }
        try {
          const silentTokens = await refreshAccessToken();
          if (silentTokens?.access_token) {
            setToken(silentTokens.access_token);
            if (silentTokens.id_token) {
              setIdToken(silentTokens.id_token);
            }
            // Fall through to the user-load block below using the new token.
            // Re-triggering bootstrap via setToken will re-run this effect.
            return;
          }
        } catch (_silentError) {
          // No valid cookie — user is not authenticated.
        }
        setIsLoading(false);
        return;
      }

      try {
        await syncUser(idToken || token);
        const me = await getCurrentUser(token);
        let myTenants = [];

        try {
          myTenants = await listMyTenants(token);
        } catch (tenantError) {
          const tenantDetail = tenantError?.response?.data?.detail;
          setAuthError(
            tenantDetail
              ? `Signed in, but tenant list could not be loaded: ${tenantDetail}`
              : "Signed in, but tenant list could not be loaded.",
          );
        }

        setUser(me);
        setTenants(Array.isArray(myTenants) ? myTenants : []);

        if (!tenantId && myTenants.length > 0) {
          const firstTenant = myTenants[0].id;
          setTenantId(firstTenant);
          writeStorage(TENANT_KEY, firstTenant);
        }
        setAuthError("");

        // Redirect only to safe invitation paths and clear stale values.
        const redirectPath = readStorage(POST_LOGIN_REDIRECT_KEY) || readStorage(LEGACY_STORAGE_KEYS.postLoginRedirect);
        const isSafeInviteRedirect = isSafeInvitePath(redirectPath);
        if (isSafeInviteRedirect && redirectPath !== window.location.pathname) {
          removeStorage(POST_LOGIN_REDIRECT_KEY);
          removeStorage(LEGACY_STORAGE_KEYS.postLoginRedirect);
          window.location.href = redirectPath;
          return;
        }
        if (redirectPath && !isSafeInviteRedirect) {
          removeStorage(POST_LOGIN_REDIRECT_KEY);
          removeStorage(LEGACY_STORAGE_KEYS.postLoginRedirect);
        }
      } catch (error) {
        const authDetail = error?.response?.data?.detail;
        removeStorage(TENANT_KEY);
        setToken(null);
        setIdToken(null);
        setTenantId(null);
        setUser(null);
        setTenants([]);
        setAuthError(
          authDetail
            ? `Session invalid or expired: ${authDetail}`
            : "Session invalid or expired. Please sign in again.",
        );
      } finally {
        setIsLoading(false);
      }
    }

    bootstrap();
  }, [token, idToken]);

  // Auto-refresh token before expiry
  useEffect(() => {
    if (!token) {
      return;
    }

    const checkAndRefreshToken = async () => {
      const decoded = decodeJwt(token);
      if (!decoded || !decoded.exp) {
        return;
      }

      const expiryTime = decoded.exp * 1000; // Convert to milliseconds
      const currentTime = Date.now();
      const timeUntilExpiry = expiryTime - currentTime;

      // If token expires in less than 5 minutes, refresh it
      if (timeUntilExpiry <= REFRESH_BEFORE_EXPIRY_MS && timeUntilExpiry > 0) {
        try {
          const newTokens = await refreshAccessToken();
          if (newTokens.access_token) {
            setToken(newTokens.access_token);
            if (newTokens.id_token) {
              setIdToken(newTokens.id_token);
            }

            // Cognito rarely rotates the refresh token, but if it does,
            // the backend /auth/token/refresh endpoint already rotated the cookie.
            // We still rotate the server-side session record to match.
            if (newTokens.refresh_token && sessionId) {
              try {
                // refreshTokens still needed here to get the old token for rotation proof
                const rotated = await rotateSession(
                  newTokens.access_token,
                  sessionId,
                  newTokens.refresh_token, // best we have; cookie handles true rotation
                  newTokens.refresh_token,
                  { user_agent: navigator.userAgent },
                );
                setSessionId(rotated.session_id);
              } catch (_rotateError) {
                // Rotation is best-effort; token is still updated locally.
              }
            }
          }
        } catch (error) {
          console.error('Token refresh failed:', error);
          // Logout if refresh fails
          logout();
        }
      }
    };

    // Check immediately
    checkAndRefreshToken();

    // Set up periodic check
    refreshTimerRef.current = setInterval(checkAndRefreshToken, CHECK_INTERVAL_MS);

    return () => {
      if (refreshTimerRef.current) {
        clearInterval(refreshTimerRef.current);
      }
    };
  }, [token]);

  const loginWithToken = async (nextToken, nextRefreshToken = null) => {
    setToken(nextToken);
    setAuthError("");
  };

  const logout = async () => {
    // Clear refresh timer
    if (refreshTimerRef.current) {
      clearInterval(refreshTimerRef.current);
    }

    // Best-effort server-side revocation before local sign-out.
    if (token) {
      try {
        await revokeAllSessions(token, sessionId);
      } catch (_error) {
        // Continue local logout even if API revocation fails.
      }
    }

    // Clear HttpOnly refresh cookie server-side.
    try {
      await clearRefreshCookie();
    } catch (_error) {
      // Continue local cleanup.
    }

    // Defensively clear any legacy localStorage keys.
    // Prevent an immediate bootstrap refresh attempt after explicit logout.
    skipNextBootstrapRefreshRef.current = true;
    removeStorage(LEGACY_STORAGE_KEYS.accessToken);
    removeStorage(LEGACY_STORAGE_KEYS.idToken);
    removeStorage(LEGACY_STORAGE_KEYS.refreshToken);
    removeStorage(TENANT_KEY);
    removeStorage(POST_LOGIN_REDIRECT_KEY);
    removeStorage(LEGACY_STORAGE_KEYS.postLoginRedirect);
    setToken(null);
    setIdToken(null);
    setTenantId(null);
    setUser(null);
    setTenants([]);
    setSessionId(null);
    setAuthError("");
    // Redirect to Cognito logout after React finishes current render
    setTimeout(() => logoutFromCognito(), 0);
  };

  const changeTenant = (nextTenantId) => {
    setTenantId(nextTenantId);
    writeStorage(TENANT_KEY, nextTenantId);
  };

  const refreshAuthState = async () => {
    if (!token) {
      return;
    }

    setIsLoading(true);
    try {
      await syncUser(idToken || token);
      const me = await getCurrentUser(token);
      const myTenants = await listMyTenants(token);
      setUser(me);
      setTenants(Array.isArray(myTenants) ? myTenants : []);
      if (!tenantId && myTenants.length > 0) {
        const firstTenant = myTenants[0].id;
        setTenantId(firstTenant);
        writeStorage(TENANT_KEY, firstTenant);
      }
      setAuthError("");
    } catch (error) {
      const authDetail = error?.response?.data?.detail;
      setAuthError(
        authDetail
          ? `Could not refresh auth state: ${authDetail}`
          : "Could not refresh auth state.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  const value = useMemo(
    () => ({
      token,
      user,
      tenants,
      tenantId,
      authError,
      isLoading,
      sessionId,
      isAuthenticated: Boolean(token && user),
      loginWithToken,
      logout,
      changeTenant,
      refreshAuthState,
    }),
    [token, user, tenants, tenantId, authError, isLoading, sessionId],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
