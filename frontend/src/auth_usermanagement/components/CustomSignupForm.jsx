/**
 * Custom Signup Form — used when VITE_AUTH_MODE=custom_ui.
 *
 * Handles both the signup step and the email confirmation step.
 * After signup, Cognito sends a verification code to the user's email.
 * The user enters it to confirm, then can sign in.
 */
import { useState } from "react";
import { customSignup, customConfirmEmail, customResendCode } from "../services/customAuthApi";

export function CustomSignupForm({ onConfirmed, onSwitchToLogin }) {
  const [step, setStep] = useState("signup"); // "signup" | "confirm"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [resendLoading, setResendLoading] = useState(false);

  const handleSignup = async (e) => {
    e.preventDefault();
    if (!email.trim() || !password) return;

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const result = await customSignup(email.trim(), password);

      if (result.confirmed) {
        // Auto-confirmed (pool setting or pre-verified via invite)
        onConfirmed?.(email.trim());
      } else {
        // Need email confirmation
        setStep("confirm");
      }
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Signup failed");
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async (e) => {
    e.preventDefault();
    if (!code.trim()) return;

    setLoading(true);
    setError("");

    try {
      await customConfirmEmail(email.trim(), code.trim());
      onConfirmed?.(email.trim());
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Confirmation failed");
    } finally {
      setLoading(false);
    }
  };

  const handleResendCode = async () => {
    setResendLoading(true);
    setError("");
    try {
      await customResendCode(email.trim());
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to resend code");
    } finally {
      setResendLoading(false);
    }
  };

  if (step === "confirm") {
    return (
      <form onSubmit={handleConfirm} style={styles.form}>
        <h2 style={styles.title}>Verify Your Email</h2>
        <p style={styles.subtitle}>
          We sent a verification code to <strong>{email}</strong>.
        </p>

        <label htmlFor="confirm-code" style={styles.label}>Confirmation Code</label>
        <input
          id="confirm-code"
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

        {error && <p style={styles.error}>{error}</p>}

        <button type="submit" disabled={loading} style={styles.button}>
          {loading ? "Confirming..." : "Confirm Email"}
        </button>

        <button
          type="button"
          onClick={handleResendCode}
          disabled={resendLoading}
          style={styles.linkButton}
        >
          {resendLoading ? "Sending..." : "Resend code"}
        </button>
      </form>
    );
  }

  return (
    <form onSubmit={handleSignup} style={styles.form}>
      <h2 style={styles.title}>Create Account</h2>

      <label htmlFor="signup-email" style={styles.label}>Email</label>
      <input
        id="signup-email"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
        autoComplete="email"
        disabled={loading}
        style={styles.input}
        placeholder="you@example.com"
      />

      <label htmlFor="signup-password" style={styles.label}>Password</label>
      <input
        id="signup-password"
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

      <label htmlFor="signup-confirm" style={styles.label}>Confirm Password</label>
      <input
        id="signup-confirm"
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
        {loading ? "Creating account..." : "Sign Up"}
      </button>

      {onSwitchToLogin && (
        <p style={styles.switchText}>
          Already have an account?{" "}
          <button type="button" onClick={onSwitchToLogin} style={styles.linkButton}>
            Sign in
          </button>
        </p>
      )}
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
