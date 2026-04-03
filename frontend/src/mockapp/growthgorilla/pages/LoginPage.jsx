import { useMemo, useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { CustomLoginForm, ForgotPasswordForm, useAuth } from "../../../auth_usermanagement";
import { getHostedLoginUrl } from "../../../auth_usermanagement/services/cognitoClient";
import { FunnelBanner } from "../components/FunnelBanner";
import { theme, componentStyles } from "../theme";

function appendIdentityProvider(url, providerName) {
  const urlObj = new URL(url);
  urlObj.searchParams.set("identity_provider", providerName);
  return urlObj.toString();
}

export function LoginPage() {
  const { isAuthenticated, loginWithTokens } = useAuth();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [mode, setMode] = useState("login");
  const [socialLoading, setSocialLoading] = useState("");

  const initialEmail = useMemo(() => searchParams.get("email") || "", [searchParams]);

  if (isAuthenticated) {
    return <Navigate to="/onboarding" replace />;
  }

  const startSocialLogin = async (providerName) => {
    setSocialLoading(providerName);
    try {
      const baseUrl = await getHostedLoginUrl();
      window.location.href = appendIdentityProvider(baseUrl, providerName);
    } catch (_error) {
      setSocialLoading("");
    }
  };

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <FunnelBanner />

        <div style={styles.header}>
          <h2 style={styles.title}>Welcome Back</h2>
          <p style={styles.subtitle}>
            Sign in to continue to GrowthGorilla
          </p>
        </div>

        <div style={styles.socialRow}>
          <button
            style={styles.socialButton}
            disabled={Boolean(socialLoading)}
            onClick={() => startSocialLogin("Google")}
          >
            {socialLoading === "Google" ? "Redirecting..." : "Google"}
          </button>
          <button
            style={styles.socialButton}
            disabled={Boolean(socialLoading)}
            onClick={() => startSocialLogin("Microsoft")}
          >
            {socialLoading === "Microsoft" ? "Redirecting..." : "Microsoft"}
          </button>
        </div>

        <div style={styles.divider}>or email</div>

        {mode === "forgot" ? (
          <ForgotPasswordForm
            initialEmail={initialEmail}
            onBackToLogin={() => setMode("login")}
          />
        ) : (
          <CustomLoginForm
            initialEmail={initialEmail}
            onSuccess={async (tokens) => {
              await loginWithTokens(tokens);
              navigate("/onboarding");
            }}
            onSwitchToSignup={() => navigate("/signup")}
            onForgotPassword={() => setMode("forgot")}
            onNewPasswordRequired={() => {
              setMode("forgot");
            }}
          />
        )}
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: "100vh",
    padding: theme.spacing.lg,
    display: "grid",
    placeItems: "center",
    background: `linear-gradient(165deg, #f0f9ff, #fff8f0)`,
  },
  card: {
    width: "min(560px, 100%)",
    background: theme.colors.background,
    borderRadius: theme.radius.xl,
    border: `1px solid ${theme.colors.border}`,
    padding: theme.spacing.xl,
    boxShadow: theme.shadows.lg,
  },
  header: {
    marginBottom: theme.spacing.xl,
    textAlign: "center",
  },
  title: {
    margin: 0,
    fontSize: theme.fonts.sizes['2xl'],
    fontWeight: theme.fonts.weights.bold,
    color: theme.colors.primaryDark,
  },
  subtitle: {
    margin: `${theme.spacing.md}px 0 0`,
    fontSize: theme.fonts.sizes.base,
    color: theme.colors.text.secondary,
  },
  socialRow: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: theme.spacing.md,
    marginBottom: theme.spacing.lg,
  },
  socialButton: {
    ...componentStyles.button,
    border: `1px solid ${theme.colors.border}`,
    borderRadius: theme.radius.lg,
    background: theme.colors.surface,
    color: theme.colors.text.primary,
    fontWeight: theme.fonts.weights.semibold,
    transition: theme.transitions.fast,
    "&:hover": {
      background: theme.colors.background,
      borderColor: theme.colors.primary,
    },
  },
  divider: {
    margin: `${theme.spacing.lg}px 0`,
    textAlign: "center",
    color: theme.colors.text.tertiary,
    fontSize: theme.fonts.sizes.xs,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
  },
};
