import { useNavigate } from "react-router-dom";
import { FunnelBanner } from "../components/FunnelBanner";
import { getFunnelContext } from "../state/funnelContext";
import { theme, componentStyles } from "../theme";

export function PurchasePage() {
  const navigate = useNavigate();
  const context = getFunnelContext();
  const offerLabel = context?.offer?.label || "No offer selected";

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <FunnelBanner />

        <div style={componentStyles.hero}>
          <p style={componentStyles.kicker}>Payment</p>
          <h1 style={componentStyles.heading}>Complete Your Purchase</h1>
          <p style={componentStyles.body}>
            Your wheel result is applied below. This is a mock purchase step for the POC.
          </p>
        </div>

        <div style={styles.offerBox}>
          <p style={styles.offerLabel}>Your offer</p>
          <p style={styles.offerValue}>{offerLabel}</p>
        </div>

        <button style={styles.payNow} onClick={() => navigate("/onboarding")}>Pay Now</button>
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
    background: "linear-gradient(165deg, #fff7ed, #eff6ff)",
  },
  card: {
    width: "min(640px, 100%)",
    background: theme.colors.background,
    borderRadius: theme.radius.xl,
    border: `1px solid ${theme.colors.border}`,
    padding: theme.spacing["2xl"],
    boxShadow: theme.shadows.lg,
  },
  offerBox: {
    border: `1px solid ${theme.colors.accent}`,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.xl,
    background: "#f8fafc",
    marginBottom: theme.spacing.xl,
    textAlign: "center",
  },
  offerLabel: {
    margin: 0,
    color: theme.colors.text.secondary,
    fontSize: theme.fonts.sizes.sm,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    fontWeight: theme.fonts.weights.bold,
  },
  offerValue: {
    margin: `${theme.spacing.sm}px 0 0`,
    color: theme.colors.primaryDark,
    fontSize: theme.fonts.sizes["2xl"],
    fontWeight: theme.fonts.weights.bold,
  },
  payNow: {
    width: "100%",
    border: "none",
    borderRadius: theme.radius.lg,
    padding: `${theme.spacing.md}px ${theme.spacing.lg}px`,
    background: theme.colors.primary,
    color: "#fff",
    fontSize: theme.fonts.sizes.lg,
    fontWeight: theme.fonts.weights.bold,
    cursor: "pointer",
  },
};
