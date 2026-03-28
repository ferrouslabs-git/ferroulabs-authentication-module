/**
 * Custom UI auth API client.
 *
 * Calls the backend /auth/custom/* endpoints which proxy Cognito
 * USER_PASSWORD_AUTH flow.  Used when VITE_AUTH_MODE=custom_ui.
 *
 * The backend handles all Cognito SDK calls — the frontend never
 * needs AWS credentials.
 */
import axios from "axios";
import { AUTH_CONFIG } from "../config";

const api = axios.create({
  baseURL: AUTH_CONFIG.apiBasePath,
  timeout: 15000,
});

/**
 * Login with email + password.
 * Returns { authenticated, access_token, id_token, refresh_token, expires_in }
 * OR { authenticated: false, challenge: "NEW_PASSWORD_REQUIRED", session }
 */
export async function customLogin(email, password) {
  const res = await api.post("/custom/login", { email, password });
  return res.data;
}

/**
 * Self-service signup.
 * Returns { user_sub, confirmed, needs_confirmation }
 */
export async function customSignup(email, password) {
  const res = await api.post("/custom/signup", { email, password });
  return res.data;
}

/**
 * Confirm email with verification code (after signup).
 */
export async function customConfirmEmail(email, code) {
  const res = await api.post("/custom/confirm", { email, code });
  return res.data;
}

/**
 * Complete NEW_PASSWORD_REQUIRED challenge (invited user sets password).
 * Returns { authenticated, access_token, id_token, refresh_token, expires_in }
 */
export async function customSetPassword(email, newPassword, session) {
  const res = await api.post("/custom/set-password", {
    email,
    new_password: newPassword,
    session,
  });
  return res.data;
}

/**
 * Resend email confirmation code.
 */
export async function customResendCode(email) {
  const res = await api.post("/custom/resend-code", { email });
  return res.data;
}

/**
 * Initiate forgot-password — sends reset code to user's email.
 */
export async function customForgotPassword(email) {
  const res = await api.post("/custom/forgot-password", { email });
  return res.data;
}

/**
 * Complete forgot-password with reset code + new password.
 */
export async function customConfirmForgotPassword(email, code, newPassword) {
  const res = await api.post("/custom/confirm-forgot-password", {
    email,
    code,
    new_password: newPassword,
  });
  return res.data;
}
