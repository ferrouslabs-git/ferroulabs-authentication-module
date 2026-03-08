import { useState } from "react";
import { openHostedLogin } from "../services/cognitoClient";

export function LoginForm({ className, renderHeader, onSubmitToken, isLoading, authError }) {
  const [token, setToken] = useState("");
  const [redirecting, setRedirecting] = useState(false);
  const [redirectError, setRedirectError] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!token.trim()) {
      return;
    }
    await onSubmitToken(token.trim());
  };

  const handleHostedLogin = async () => {
    setRedirectError("");
    setRedirecting(true);
    try {
      await openHostedLogin();
    } catch (error) {
      setRedirectError(error?.message || "Unable to start Cognito sign-in");
      setRedirecting(false);
    }
  };

  return (
    <form className={className} onSubmit={handleSubmit}>
      {renderHeader ? renderHeader() : <h2>Sign In</h2>}
      <p style={{ marginBottom: 8 }}>
        Use Cognito Hosted UI to sign in. Redirect callback exchange is automatic.
      </p>
      <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
        <button type="button" onClick={handleHostedLogin} disabled={isLoading || redirecting}>
          {redirecting ? "Redirecting..." : "Open Cognito Sign-In"}
        </button>
      </div>
      {authError ? <p style={{ color: "#b00020", marginBottom: 8 }}>{authError}</p> : null}
      {redirectError ? <p style={{ color: "#b00020", marginBottom: 8 }}>{redirectError}</p> : null}

      <p style={{ marginBottom: 8 }}>
        Fallback: paste an ID token manually if needed for local troubleshooting.
      </p>
      <label htmlFor="id-token" style={{ display: "block", marginBottom: 6 }}>
        ID Token
      </label>
      <textarea
        id="id-token"
        value={token}
        onChange={(e) => setToken(e.target.value)}
        rows={6}
        style={{ width: "100%", marginBottom: 8 }}
        placeholder="Paste id_token here"
      />
      <button type="submit" disabled={isLoading || !token.trim()}>
        {isLoading ? "Signing in..." : "Continue"}
      </button>
    </form>
  );
}
