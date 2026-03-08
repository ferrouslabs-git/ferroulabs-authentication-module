import { createContext, useEffect, useMemo, useState, useRef } from "react";
import { getCurrentUser, listMyTenants, revokeAllSessions, syncUser } from "../services/authApi";
import {
  clearCodeFromUrl,
  exchangeAuthCodeForTokens,
  getAuthErrorFromUrl,
  getCodeFromUrl,
  logoutFromCognito,
  refreshTokens,
  decodeJwt,
} from "../services/cognitoClient";

export const AuthContext = createContext(null);

const TOKEN_KEY = "trustos_id_token";
const REFRESH_TOKEN_KEY = "trustos_refresh_token";
const TENANT_KEY = "trustos_tenant_id";
const REFRESH_BEFORE_EXPIRY_MS = 5 * 60 * 1000; // 5 minutes
const CHECK_INTERVAL_MS = 60 * 1000; // Check every minute

export function AuthProvider({ children }) {
  const [token, setToken] = useState(localStorage.getItem(TOKEN_KEY));
  const [refreshToken, setRefreshToken] = useState(localStorage.getItem(REFRESH_TOKEN_KEY));
  const [user, setUser] = useState(null);
  const [tenants, setTenants] = useState([]);
  const [tenantId, setTenantId] = useState(localStorage.getItem(TENANT_KEY));
  const [isLoading, setIsLoading] = useState(true);
  const [authError, setAuthError] = useState("");
  const refreshTimerRef = useRef(null);

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
            if (!tokens.id_token) {
              throw new Error("Cognito token response missing id_token");
            }

            localStorage.setItem(TOKEN_KEY, tokens.id_token);
            if (tokens.refresh_token) {
              localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
              setRefreshToken(tokens.refresh_token);
            }
            setToken(tokens.id_token);
            setAuthError("");
          } catch (error) {
            setAuthError(error?.message || "Unable to exchange auth code");
          }
          return;
        }
      }

      if (!token) {
        setIsLoading(false);
        return;
      }

      try {
        await syncUser(token);
        const me = await getCurrentUser(token);
        const myTenants = await listMyTenants(token);

        setUser(me);
        setTenants(myTenants);

        if (!tenantId && myTenants.length > 0) {
          const firstTenant = myTenants[0].id;
          setTenantId(firstTenant);
          localStorage.setItem(TENANT_KEY, firstTenant);
        }
        setAuthError("");

        // Check if we need to redirect after login (e.g., from invitation page)
        const redirectPath = localStorage.getItem('trustos_post_login_redirect');
        if (redirectPath && redirectPath !== window.location.pathname) {
          localStorage.removeItem('trustos_post_login_redirect');
          window.location.href = redirectPath;
        }
      } catch (error) {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(REFRESH_TOKEN_KEY);
        localStorage.removeItem(TENANT_KEY);
        setToken(null);
        setRefreshToken(null);
        setTenantId(null);
        setUser(null);
        setTenants([]);
        setAuthError("Session invalid or expired. Please sign in again.");
      } finally {
        setIsLoading(false);
      }
    }

    bootstrap();
  }, [token]);

  // Auto-refresh token before expiry
  useEffect(() => {
    if (!token || !refreshToken) {
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
          const newTokens = await refreshTokens(refreshToken);
          if (newTokens.id_token) {
            localStorage.setItem(TOKEN_KEY, newTokens.id_token);
            setToken(newTokens.id_token);
            
            // Update refresh token if provided (Cognito may rotate it)
            if (newTokens.refresh_token) {
              localStorage.setItem(REFRESH_TOKEN_KEY, newTokens.refresh_token);
              setRefreshToken(newTokens.refresh_token);
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
  }, [token, refreshToken]);

  const loginWithToken = async (nextToken, nextRefreshToken = null) => {
    localStorage.setItem(TOKEN_KEY, nextToken);
    setToken(nextToken);
    if (nextRefreshToken) {
      localStorage.setItem(REFRESH_TOKEN_KEY, nextRefreshToken);
      setRefreshToken(nextRefreshToken);
    }
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
        await revokeAllSessions(token);
      } catch (_error) {
        // Continue local logout even if API revocation fails.
      }
    }

    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(TENANT_KEY);
    setToken(null);
    setRefreshToken(null);
    setTenantId(null);
    setUser(null);
    setTenants([]);
    setAuthError("");
    // Redirect to Cognito logout after React finishes current render
    setTimeout(() => logoutFromCognito(), 0);
  };

  const changeTenant = (nextTenantId) => {
    setTenantId(nextTenantId);
    localStorage.setItem(TENANT_KEY, nextTenantId);
  };

  const value = useMemo(
    () => ({
      token,
      user,
      tenants,
      tenantId,
      authError,
      isLoading,
      isAuthenticated: Boolean(token && user),
      loginWithToken,
      logout,
      changeTenant,
    }),
    [token, user, tenants, tenantId, authError, isLoading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
