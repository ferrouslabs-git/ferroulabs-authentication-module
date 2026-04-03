import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../../../auth_usermanagement";
import { FunnelBanner } from "../components/FunnelBanner";
import { clearFunnelContext, getFunnelContext } from "../state/funnelContext";
import { theme, componentStyles } from "../theme";

export function DashboardPage() {
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();
  const context = getFunnelContext();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  const firstName = user?.name?.split(" ")[0] || user?.email?.split("@")[0] || "there";

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <FunnelBanner />
        <div style={componentStyles.hero}>
          <p style={componentStyles.kicker}>Dashboard</p>
          <h1 style={componentStyles.heading}>
            Welcome back, {firstName}! 👋
          </h1>
          <p style={componentStyles.body}>
            Your GrowthGorilla account is ready. Below is your funnel journey context captured during signup.
          </p>
        </div>

        <div style={styles.summary}>
          <h3 style={styles.summaryTitle}>📊 Your Journey</h3>
          <p style={styles.summaryDescription}>
            This is the funnel context that persisted through the signup and login process:
          </p>
          {context ? (
            <div style={styles.contextViewer}>
              <div style={styles.contextRow}>
                <span style={styles.label}>Splash Page:</span>
                <span style={styles.value}>{context.splashId}</span>
              </div>
              <div style={styles.contextRow}>
                <span style={styles.label}>Module:</span>
                <span style={styles.value}>{context.moduleTarget}</span>
              </div>
              {context.offer && (
                <div style={styles.contextRow}>
                  <span style={styles.label}>Your Offer:</span>
                  <span style={styles.value}>{context.offer.label}</span>
                </div>
              )}
              <div style={styles.contextRow}>
                <span style={styles.label}>Captured At:</span>
                <span style={styles.value}>{new Date(context.capturedAt).toLocaleString()}</span>
              </div>
            </div>
          ) : (
            <p style={styles.noContext}>No funnel context captured. Start from the splash page.</p>
          )}
          <details style={styles.details}>
            <summary style={styles.summary}>Raw JSON</summary>
            <pre style={styles.pre}>{JSON.stringify(context || {}, null, 2)}</pre>
          </details>
        </div>

        <div style={styles.nextSteps}>
          <h3 style={styles.stepsTitle}>Next Steps</h3>
          <ul style={styles.stepsList}>
            <li>Complete your profile setup</li>
            <li>Invite your team members</li>
            <li>Launch your first module to start growing</li>
          </ul>
        </div>

        <div style={styles.actions}>
          <button 
            style={styles.primary} 
            onClick={() => navigate("/splash/S1")}
          >
            Explore Other Offers
          </button>
          <button
            style={styles.secondary}
            onClick={() => {
              clearFunnelContext();
              navigate("/splash/S1");
            }}
          >
            Clear Journey & Restart
          </button>
          <button style={styles.ghost} onClick={() => logout()}>
            Sign Out
          </button>
        </div>
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
    background: `linear-gradient(165deg, #f5f8ff, #eefbf5)`,
  },
  card: {
    width: "min(860px, 100%)",
    background: theme.colors.background,
    borderRadius: theme.radius.xl,
    border: `1px solid ${theme.colors.border}`,
    padding: theme.spacing['2xl'],
    boxShadow: theme.shadows.lg,
  },
  summary: {
    marginTop: theme.spacing['2xl'],
    border: `1px solid ${theme.colors.border}`,
    borderRadius: theme.radius.lg,
    background: theme.colors.surface,
    padding: theme.spacing.lg,
  },
  summaryTitle: {
    marginTop: 0,
    marginBottom: theme.spacing.md,
    color: theme.colors.primaryDark,
    fontSize: theme.fonts.sizes.lg,
    fontWeight: theme.fonts.weights.semibold,
  },
  summaryDescription: {
    margin: `0 0 ${theme.spacing.lg}px`,
    color: theme.colors.text.secondary,
    fontSize: theme.fonts.sizes.sm,
  },
  contextViewer: {
    marginBottom: theme.spacing.lg,
    background: theme.colors.background,
    borderRadius: theme.radius.md,
    padding: theme.spacing.lg,
    border: `1px solid ${theme.colors.border}`,
  },
  contextRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: `${theme.spacing.md}px 0`,
    borderBottom: `1px solid ${theme.colors.border}`,
    "&:last-child": {
      borderBottom: "none",
    },
  },
  label: {
    fontWeight: theme.fonts.weights.semibold,
    color: theme.colors.text.primary,
    fontSize: theme.fonts.sizes.sm,
  },
  value: {
    color: theme.colors.primary,
    fontWeight: theme.fonts.weights.bold,
    fontSize: theme.fonts.sizes.base,
    fontFamily: "monospace",
  },
  noContext: {
    margin: 0,
    color: theme.colors.text.secondary,
    fontSize: theme.fonts.sizes.sm,
    fontStyle: "italic",
  },
  details: {
    marginTop: theme.spacing.md,
  },
  details_summary: {
    cursor: "pointer",
    color: theme.colors.primary,
    fontWeight: theme.fonts.weights.semibold,
    fontSize: theme.fonts.sizes.sm,
    userSelect: "none",
  },
  pre: {
    marginTop: theme.spacing.md,
    padding: theme.spacing.md,
    background: theme.colors.background,
    borderRadius: theme.radius.md,
    border: `1px solid ${theme.colors.border}`,
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    color: theme.colors.text.primary,
    fontSize: "12px",
    fontFamily: "monospace",
    overflow: "auto",
    maxHeight: 200,
  },
  nextSteps: {
    marginTop: theme.spacing['2xl'],
  },
  stepsTitle: {
    margin: 0,
    color: theme.colors.primaryDark,
    fontSize: theme.fonts.sizes.lg,
    fontWeight: theme.fonts.weights.semibold,
    marginBottom: theme.spacing.md,
  },
  stepsList: {
    margin: 0,
    paddingLeft: theme.spacing.xl,
    color: theme.colors.text.secondary,
    lineHeight: 1.8,
  },
  actions: {
    marginTop: theme.spacing['2xl'],
    display: "flex",
    gap: theme.spacing.md,
    flexDirection: "column",
  },
  primary: {
    ...componentStyles.button,
    ...componentStyles.buttonPrimary,
    fontSize: theme.fonts.sizes.base,
  },
  secondary: {
    ...componentStyles.button,
    ...componentStyles.buttonSecondary,
    fontSize: theme.fonts.sizes.base,
  },
  ghost: {
    ...componentStyles.button,
    background: theme.colors.surface,
    color: theme.colors.text.secondary,
    border: `1px solid ${theme.colors.border}`,
    fontSize: theme.fonts.sizes.base,
  },
};
