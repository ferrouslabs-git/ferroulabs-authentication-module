import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../../../auth_usermanagement";
import { FunnelBanner } from "../components/FunnelBanner";
import { theme, componentStyles } from "../theme";

export function OnboardingPage() {
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  const firstName = user?.name?.split(" ")[0] || user?.email?.split("@")[0] || "there";

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <FunnelBanner />
        <div style={componentStyles.hero}>
          <p style={componentStyles.kicker}>Welcome Aboard</p>
          <h1 style={componentStyles.heading}>
            You're All Set, {firstName}! 🎉
          </h1>
          <p style={componentStyles.body}>
            Your account is ready. Let's set up your workspace and get you started.
          </p>
        </div>

        <div style={styles.setupSection}>
          <div style={styles.setupStep}>
            <span style={styles.stepNumber}>1</span>
            <div>
              <h3 style={styles.stepTitle}>Complete Your Profile</h3>
              <p style={styles.stepDescription}>Add your photo and company details</p>
            </div>
          </div>
          <div style={styles.setupStep}>
            <span style={styles.stepNumber}>2</span>
            <div>
              <h3 style={styles.stepTitle}>Connect Your Team</h3>
              <p style={styles.stepDescription}>Invite team members to collaborate</p>
            </div>
          </div>
          <div style={styles.setupStep}>
            <span style={styles.stepNumber}>3</span>
            <div>
              <h3 style={styles.stepTitle}>Launch Your First Module</h3>
              <p style={styles.stepDescription}>Start with your selected module</p>
            </div>
          </div>
        </div>

        <div style={styles.actions}>
          <button style={styles.primary} onClick={() => navigate("/dashboard")}>
            Continue to Dashboard →
          </button>
          <button style={styles.secondary} onClick={() => navigate("/splash/S1")}>
            Explore Other Offers
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
    background: `linear-gradient(165deg, #eefbf5, #eff7ff)`,
  },
  card: {
    width: "min(740px, 100%)",
    background: theme.colors.background,
    borderRadius: theme.radius.xl,
    border: `1px solid ${theme.colors.border}`,
    padding: theme.spacing['2xl'],
    boxShadow: theme.shadows.lg,
  },
  setupSection: {
    marginTop: theme.spacing['2xl'],
    marginBottom: theme.spacing['2xl'],
    display: "flex",
    flexDirection: "column",
    gap: theme.spacing.lg,
  },
  setupStep: {
    display: "flex",
    gap: theme.spacing.lg,
    padding: theme.spacing.lg,
    borderRadius: theme.radius.lg,
    background: theme.colors.surface,
    border: `1px solid ${theme.colors.border}`,
  },
  stepNumber: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    width: 40,
    height: 40,
    borderRadius: "50%",
    background: theme.colors.primary,
    color: "#fff",
    fontWeight: theme.fonts.weights.bold,
    fontSize: theme.fonts.sizes.lg,
    flexShrink: 0,
  },
  stepTitle: {
    margin: 0,
    fontSize: theme.fonts.sizes.base,
    fontWeight: theme.fonts.weights.semibold,
    color: theme.colors.primaryDark,
  },
  stepDescription: {
    margin: `${theme.spacing.xs}px 0 0`,
    fontSize: theme.fonts.sizes.sm,
    color: theme.colors.text.secondary,
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
