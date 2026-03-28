/**
 * Forgot Password Form — used when VITE_AUTH_MODE=custom_ui.
 *
 * Two steps:
 * 1. Enter email → backend calls Cognito ForgotPassword → code sent
 * 2. Enter code + new password → backend calls ConfirmForgotPassword → done
 */
import { useState } from "react";
import { customForgotPassword, customConfirmForgotPassword } from "../services/customAuthApi";

export function ForgotPasswordForm({ onBackToLogin, initialEmail = "" }) {
  const [step, setStep] = useState("request"); // "request" | "confirm"
  const [email, setEmail] = useState(initialEmail);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const handleRequestCode = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;

    setLoading(true);
    setError("");

    try {
      await customForgotPassword(email.trim());
      setStep("confirm");
      setSuccess("If the account exists, a reset code has been sent to your email.");
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Failed to send reset code");
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmReset = async (e) => {
    e.preventDefault();
    if (!code.trim() || !password) return;

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
    setSuccess("");

    try {
      await customConfirmForgotPassword(email.trim(), code.trim(), password);
      setSuccess("Password reset successful!");
      // Auto-redirect to login after short delay
      setTimeout(() => onBackToLogin?.(), 1500);
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Password reset failed");
    } finally {
      setLoading(false);
    }
  };

  if (step === "confirm") {
    return (
      <form onSubmit={handleConfirmReset} style={styles.form}>
        <h2 style={styles.title}>Reset Password</h2>
        <p style={styles.subtitle}>
          Enter the code sent to <strong>{email}</strong> and choose a new password.
        </p>

        <label htmlFor="reset-code" style={styles.label}>Reset Code</label>
        <input
          id="reset-code"
          type="text"
          inputMode="numeric"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          required
          disabled={loading}
          style={styles.input}
          placeholder="Enter 6-digit code"
          autoComplete="one-time-code"
        />

        <label htmlFor="reset-new-password" style={styles.label}>New Password</label>
        <input
          id="reset-new-password"
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

        <label htmlFor="reset-confirm-password" style={styles.label}>Confirm Password</label>
        <input
          id="reset-confirm-password"
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
        {success && <p style={styles.success}>{success}</p>}

        <button type="submit" disabled={loading} style={styles.button}>
          {loading ? "Resetting..." : "Reset Password"}
        </button>

        <button type="button" onClick={onBackToLogin} style={styles.linkButton}>
          Back to Sign In
        </button>
      </form>
    );
  }

  return (
    <form onSubmit={handleRequestCode} style={styles.form}>
      <h2 style={styles.title}>Forgot Password?</h2>
      <p style={styles.subtitle}>
        Enter your email and we'll send you a code to reset your password.
      </p>

      <label htmlFor="forgot-email" style={styles.label}>Email</label>
      <input
        id="forgot-email"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
        autoComplete="email"
        disabled={loading}
        style={styles.input}
        placeholder="you@example.com"
      />

      {error && <p style={styles.error}>{error}</p>}
      {success && <p style={styles.success}>{success}</p>}

      <button type="submit" disabled={loading} style={styles.button}>
        {loading ? "Sending..." : "Send Reset Code"}
      </button>

      <button type="button" onClick={onBackToLogin} style={styles.linkButton}>
        Back to Sign In
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
  success: { color: "#1b7a3d", margin: 0, fontSize: 14 },
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
  linkButton: {
    background: "none",
    border: "none",
    color: "#4f46e5",
    cursor: "pointer",
    fontWeight: 600,
    fontSize: 14,
    padding: 0,
    textDecoration: "underline",
    textAlign: "center",
  },
};
