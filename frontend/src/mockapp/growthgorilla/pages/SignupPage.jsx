import { Navigate, useNavigate } from "react-router-dom";
import { CustomSignupForm, useAuth } from "../../../auth_usermanagement";
import { FunnelBanner } from "../components/FunnelBanner";
import { theme, componentStyles } from "../theme";

export function SignupPage() {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();

  if (isAuthenticated) {
    return <Navigate to="/purchase" replace />;
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <FunnelBanner />
        <div style={styles.header}>
          <h2 style={styles.title}>Create Your Account</h2>
          <p style={styles.subtitle}>
            Join thousands using GrowthGorilla to accelerate their growth
          </p>
        </div>
        <CustomSignupForm
          onConfirmed={() => {
            navigate("/purchase");
          }}
        />
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
    background: `linear-gradient(160deg, #f2f7ff, #f4fdf7)`,
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
};
