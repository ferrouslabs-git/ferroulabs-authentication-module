import { Link } from "react-router-dom";
import { theme } from "../theme";

export function FlowEntryPage() {
  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <p style={styles.kicker}>GrowthGorilla</p>
        <h1 style={styles.title}>Choose Your Route</h1>
        <p style={styles.subtitle}>
          Select how you want to enter the mock experience.
        </p>

        <div style={styles.actions}>
          <Link to="/normal" style={{ ...styles.cta, ...styles.primary }}>
            Normal Route
          </Link>
          <Link to="/splash" style={{ ...styles.cta, ...styles.secondary }}>
            Splash Route
          </Link>
        </div>
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: "100vh",
    display: "grid",
    placeItems: "center",
    padding: theme.spacing.lg,
    background: "linear-gradient(165deg, #f0f9ff, #fff7ed)",
  },
  card: {
    width: "min(420px, 100%)",
    background: theme.colors.background,
    border: `1px solid ${theme.colors.border}`,
    borderRadius: theme.radius.xl,
    padding: theme.spacing["2xl"],
    boxShadow: theme.shadows.lg,
    textAlign: "center",
  },
  kicker: {
    margin: 0,
    color: theme.colors.primary,
    fontWeight: theme.fonts.weights.bold,
    letterSpacing: "0.06em",
    textTransform: "uppercase",
    fontSize: theme.fonts.sizes.xs,
  },
  title: {
    margin: `${theme.spacing.md}px 0 ${theme.spacing.sm}px`,
    color: theme.colors.primaryDark,
    fontSize: theme.fonts.sizes["3xl"],
  },
  subtitle: {
    margin: 0,
    color: theme.colors.text.secondary,
    fontSize: theme.fonts.sizes.base,
  },
  actions: {
    marginTop: theme.spacing["2xl"],
    display: "grid",
    gap: theme.spacing.md,
  },
  cta: {
    minHeight: 44,
    borderRadius: theme.radius.lg,
    display: "grid",
    placeItems: "center",
    textDecoration: "none",
    fontWeight: theme.fonts.weights.bold,
    fontSize: theme.fonts.sizes.base,
  },
  primary: {
    background: theme.colors.primary,
    color: "#fff",
  },
  secondary: {
    border: `1px solid ${theme.colors.accent}`,
    color: theme.colors.primaryDark,
    background: "#fff",
  },
};
