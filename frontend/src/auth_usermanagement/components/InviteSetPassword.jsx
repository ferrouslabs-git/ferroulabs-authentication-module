/**
 * Invite Set Password Form — the core component that solves the Hosted UI limitation.
 *
 * Flow:
 * 1. Invited user clicks link in email → lands on /invite/:token
 * 2. AcceptInvitation component loads invitation details (email, tenant)
 * 3. This form shows ONLY a password field (email is pre-filled + read-only)
 * 4. On submit: calls /auth/custom/login with email + temp password from Cognito
 *    → gets NEW_PASSWORD_REQUIRED challenge → calls /auth/custom/set-password
 *    → returns real tokens → user is authenticated
 *
 * The temp_password is NOT visible to the user. The backend created it
 * during invitation and Cognito holds it internally.
 */
import { useState } from "react";
import { customLogin, customSetPassword } from "../services/customAuthApi";

export function InviteSetPassword({ email, onSuccess }) {
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [tempPassword, setTempPassword] = useState("");
  const [step, setStep] = useState("enter-temp"); // "enter-temp" | "set-password"
  const [session, setSession] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Step 1: User enters the temporary password from their invitation
  // (In practice this is provided by logging in with the temp credentials)
  const handleTempLogin = async (e) => {
    e.preventDefault();
    if (!tempPassword) return;

    setLoading(true);
    setError("");

    try {
      const result = await customLogin(email, tempPassword);

      if (result.authenticated) {
        // User was already confirmed (shouldn't happen for invites, but handle it)
        onSuccess?.({
          accessToken: result.access_token,
          idToken: result.id_token,
          refreshToken: result.refresh_token,
        });
      } else if (result.challenge === "NEW_PASSWORD_REQUIRED") {
        setSession(result.session);
        setStep("set-password");
      } else {
        setError("Unexpected response. Please contact support.");
      }
    } catch (err) {
      setError(err?.response?.data?.detail || "Invalid temporary password");
    } finally {
      setLoading(false);
    }
  };

  // Step 2: User sets their permanent password
  const handleSetPassword = async (e) => {
    e.preventDefault();
    if (!password || !confirmPassword) return;

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const result = await customSetPassword(email, password, session);

      if (result.authenticated) {
        onSuccess?.({
          accessToken: result.access_token,
          idToken: result.id_token,
          refreshToken: result.refresh_token,
        });
      } else {
        setError("Failed to set password. Please try again.");
      }
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(detail || "Failed to set password");
    } finally {
      setLoading(false);
    }
  };

  if (step === "set-password") {
    return (
      <form onSubmit={handleSetPassword} style={styles.form}>
        <h2 style={styles.title}>Set Your Password</h2>
        <p style={styles.subtitle}>
          Choose a password for <strong>{email}</strong>
        </p>

        <label htmlFor="invite-new-password" style={styles.label}>New Password</label>
        <input
          id="invite-new-password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          autoComplete="new-password"
          minLength={8}
          disabled={loading}
          style={styles.input}
          placeholder="Minimum 8 characters"
        />

        <label htmlFor="invite-confirm-password" style={styles.label}>Confirm Password</label>
        <input
          id="invite-confirm-password"
          type="password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          required
          autoComplete="new-password"
          disabled={loading}
          style={styles.input}
          placeholder="Re-enter your password"
        />

        {error && <p style={styles.error}>{error}</p>}

        <button type="submit" disabled={loading} style={styles.button}>
          {loading ? "Setting password..." : "Set Password & Continue"}
        </button>
      </form>
    );
  }

  return (
    <form onSubmit={handleTempLogin} style={styles.form}>
      <h2 style={styles.title}>Welcome!</h2>
      <p style={styles.subtitle}>
        Setting up your account for <strong>{email}</strong>
      </p>

      <label htmlFor="invite-email" style={styles.label}>Email</label>
      <input
        id="invite-email"
        type="email"
        value={email}
        readOnly
        style={{ ...styles.input, background: "#f5f5f5", color: "#666" }}
      />

      <label htmlFor="invite-temp-password" style={styles.label}>Temporary Password</label>
      <input
        id="invite-temp-password"
        type="password"
        value={tempPassword}
        onChange={(e) => setTempPassword(e.target.value)}
        required
        disabled={loading}
        style={styles.input}
        placeholder="From your invitation email"
      />

      {error && <p style={styles.error}>{error}</p>}

      <button type="submit" disabled={loading} style={styles.button}>
        {loading ? "Verifying..." : "Continue"}
      </button>
    </form>
  );
}

const styles = {
  form: { display: "flex", flexDirection: "column", gap: 12, maxWidth: 380 },
  title: { margin: "0 0 4px 0", fontSize: 22 },
  subtitle: { margin: "0 0 8px 0", fontSize: 14, color: "#555" },
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
};
