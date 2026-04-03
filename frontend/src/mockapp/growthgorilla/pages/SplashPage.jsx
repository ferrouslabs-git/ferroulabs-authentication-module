import { Link, useParams } from "react-router-dom";
import { getModuleForSplash, SPLASH_IDS } from "../constants/splashMap";
import { mergeFunnelContext } from "../state/funnelContext";
import { theme, componentStyles } from "../theme";

const moduleDescriptions = {
  module_a: "Accelerate Your Growth",
  module_b: "Build Stronger Teams",
  module_c: "Create Better Campaigns",
  module_d: "Deliver More Impact",
};

export function SplashPage() {
  const { splashId = "S1" } = useParams();
  const normalized = splashId.toUpperCase();
  const moduleTarget = getModuleForSplash(normalized);

  if (moduleTarget) {
    mergeFunnelContext({ splashId: normalized, moduleTarget });
  }

  if (!moduleTarget) {
    return (
      <div style={{ ...componentStyles.page, textAlign: "center" }}>
        <h2 style={componentStyles.heading}>You've found a mystery! 🔍</h2>
        <p style={componentStyles.body}>Select a valid splash page to continue:</p>
        <div style={styles.links}>
          {SPLASH_IDS.map((id) => (
            <Link key={id} style={styles.splashTile} to={`/splash/${id}`}>
              {id}
            </Link>
          ))}
        </div>
      </div>
    );
  }

  const moduleTitle = moduleDescriptions[moduleTarget] || moduleTarget.replace("_", " ");

  return (
    <div style={componentStyles.page}>
      <div style={componentStyles.hero}>
        <p style={componentStyles.kicker}>Limited Time Offer</p>
        <h1 style={componentStyles.heading}>
          {moduleTitle}
        </h1>
        <p style={{ ...componentStyles.subheading, color: theme.colors.secondary, marginTop: theme.spacing.lg }}>
          Spin the wheel to unlock an exclusive offer
        </p>
      </div>

      <p style={componentStyles.body}>
        You've been selected for a special promotion on {moduleTarget.replace(/_/g, " ")}. 
        Spin the wheel to discover your exclusive offer, then sign up to claim it before it expires.
      </p>

      <div style={styles.ctaSection}>
        <Link to="/wheel" style={styles.ctaPrimary}>
          🎡 Spin the Wheel
        </Link>
        <Link to="/signup" style={styles.ctaSecondary}>
          Skip to Sign Up
        </Link>
      </div>

      <div style={styles.explorationSection}>
        <p style={{ ...componentStyles.body, color: theme.colors.text.tertiary, fontSize: theme.fonts.sizes.sm }}>
          Or explore other offers:
        </p>
        <div style={styles.grid}>
          {SPLASH_IDS.map((id) => (
            <Link key={id} style={styles.tile} to={`/splash/${id}`}>
              <span style={styles.tileLabel}>{id}</span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}


const styles = {
  links: {
    display: "flex",
    gap: theme.spacing.md,
    marginTop: theme.spacing['2xl'],
    flexWrap: "wrap",
    justifyContent: "center",
  },
  ctaSection: {
    display: "flex",
    gap: theme.spacing.lg,
    marginTop: theme.spacing['2xl'],
    marginBottom: theme.spacing['3xl'],
    justifyContent: "center",
    flexWrap: "wrap",
  },
  ctaPrimary: {
    ...componentStyles.button,
    ...componentStyles.buttonPrimary,
    fontSize: theme.fonts.sizes.lg,
    padding: `${theme.spacing.lg}px ${theme.spacing['2xl']}px`,
    textDecoration: "none",
  },
  ctaSecondary: {
    ...componentStyles.button,
    ...componentStyles.buttonSecondary,
    fontSize: theme.fonts.sizes.base,
    textDecoration: "none",
  },
  explorationSection: {
    marginTop: theme.spacing['3xl'],
    paddingTop: theme.spacing['2xl'],
    borderTop: `1px solid ${theme.colors.border}`,
  },
  grid: {
    marginTop: theme.spacing.lg,
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(100px, 1fr))",
    gap: theme.spacing.md,
  },
  tile: {
    ...componentStyles.card,
    textAlign: "center",
    padding: `${theme.spacing.lg}px`,
    cursor: "pointer",
    background: theme.colors.surface,
    textDecoration: "none",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    minHeight: 80,
  },
  tileLabel: {
    color: theme.colors.primary,
    fontWeight: theme.fonts.weights.bold,
    fontSize: theme.fonts.sizes.lg,
  },
  splashTile: {
    padding: `${theme.spacing.md}px ${theme.spacing.lg}px`,
    borderRadius: theme.radius.lg,
    background: theme.colors.surface,
    color: theme.colors.primary,
    textDecoration: "none",
    fontWeight: theme.fonts.weights.semibold,
    border: `1px solid ${theme.colors.accent}`,
    cursor: "pointer",
    transition: theme.transitions.fast,
  },
};
