/**
 * Custom Login Form — used when VITE_AUTH_MODE=custom_ui.
 *
 * Renders email + password fields and calls the backend /auth/custom/login
 * endpoint.  If Cognito returns NEW_PASSWORD_REQUIRED (invited user), the
 * onNewPasswordRequired callback is fired so the parent can show the
 * set-password form.
 */
import { useState } from "react";
import { customLogin } from "../services/customAuthApi";

export function CustomLoginForm({
  onSuccess,
  onNewPasswordRequired,
  onSwitchToSignup,
  onForgotPassword,
  initialEmail = "",
}) {
  const [email, setEmail] = useState(initialEmail);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim() || !password) return;

    setLoading(true);
    setError("");

    try {
      const result = await customLogin(email.trim(), password);

      if (result.authenticated) {
        onSuccess?.({
          accessToken: result.access_token,
          idToken: result.id_token,
          refreshToken: result.refresh_token,
          expiresIn: result.expires_in,
        });
      } else if (result.challenge === "NEW_PASSWORD_REQUIRED") {
        onNewPasswordRequired?.({
          email: email.trim(),
          session: result.session,
        });
      } else {
        setError("Unexpected response. Please try again.");
      }
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(detail || err?.message || "Sign in failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} style={styles.form}>
      <h2 style={styles.title}>Sign In</h2>

      <label htmlFor="custom-login-email" style={styles.label}>Email</label>
      <input
        id="custom-login-email"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
        autoComplete="email"
        disabled={loading}
        style={styles.input}
        placeholder="you@example.com"
      />

      <label htmlFor="custom-login-password" style={styles.label}>Password</label>
      <input
        id="custom-login-password"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
        autoComplete="current-password"
        disabled={loading}
        style={styles.input}
        placeholder="Enter your password"
      />

      {error && <p style={styles.error}>{error}</p>}

      <button type="submit" disabled={loading} style={styles.button}>
        {loading ? "Signing in..." : "Sign In"}
      </button>

      {onForgotPassword && (
        <p style={styles.switchText}>
          <button type="button" onClick={onForgotPassword} style={styles.linkButton}>
            Forgot password?
          </button>
        </p>
      )}

      {onSwitchToSignup && (
        <p style={styles.switchText}>
          Don't have an account?{" "}
          <button type="button" onClick={onSwitchToSignup} style={styles.linkButton}>
            Sign up
          </button>
        </p>
      )}
    </form>
  );
}

const styles = {
  form: { display: "flex", flexDirection: "column", gap: 12, maxWidth: 380 },
  title: { margin: "0 0 8px 0", fontSize: 22 },
  label: { fontWeight: 600, fontSize: 14 },
  input: {
    padding: "10px 12px",
    borderRadius: 6,
    border: "1px solid #ccc",
    fontSize: 15,
    outline: "none",
  },
  error: { color: "#b00020", margin: 0, fontSize: 14 },
  button: {
    padding: "10px 20px",
    borderRadius: 6,
    border: "none",
    background: "#4f46e5",
    color: "#fff",
    fontWeight: 600,
    fontSize: 15,
    cursor: "pointer",
    marginTop: 4,
  },
  switchText: { fontSize: 14, textAlign: "center", marginTop: 8 },
  linkButton: {
    background: "none",
    border: "none",
    color: "#4f46e5",
    cursor: "pointer",
    fontWeight: 600,
    fontSize: 14,
    padding: 0,
    textDecoration: "underline",
  },
};
