import { Link, useNavigate } from "react-router-dom";
import { useState } from "react";
import { pickRandomOffer, OFFERS } from "../constants/offers";
import { getFunnelContext, mergeFunnelContext } from "../state/funnelContext";
import { theme, componentStyles } from "../theme";

export function WheelPage() {
  const navigate = useNavigate();
  const context = getFunnelContext();
  const [offer, setOffer] = useState(context?.offer || null);
  const [spinning, setSpinning] = useState(false);

  const handleSpin = () => {
    if (spinning) return;
    setSpinning(true);
    window.setTimeout(() => {
      const selected = pickRandomOffer();
      setOffer(selected);
      mergeFunnelContext({ offer: selected });
      setSpinning(false);
    }, 900);
  };

  const handleContinue = () => {
    navigate("/signup");
  };

  return (
    <div style={componentStyles.page}>
      <div style={componentStyles.hero}>
        <p style={componentStyles.kicker}>Your Lucky Day</p>
        <h1 style={componentStyles.heading}>Spin to Win!</h1>
        <p style={componentStyles.body}>
          You've unlocked the wheel. Spin once to claim your exclusive offer.
        </p>
      </div>

      <div style={styles.wheelCard}>
        <div style={styles.wheelContainer}>
          <div style={styles.wheelVisual}>
            {OFFERS.map((o, i) => (
              <div key={i} style={{ ...styles.offerSlice, transform: `rotate(${i * 120}deg)` }}>
                <span style={styles.offerLabel}>{o.label}</span>
              </div>
            ))}
          </div>
          <div style={styles.pointer} />
        </div>

        <button 
          onClick={handleSpin} 
          disabled={spinning} 
          style={{ 
            ...styles.spinButton,
            opacity: spinning ? 0.7 : 1,
            cursor: spinning ? "not-allowed" : "pointer",
          }}
        >
          {spinning ? "🎡 Spinning..." : "🎡 Spin the Wheel"}
        </button>

        {offer ? (
          <div style={styles.resultBox}>
            <p style={styles.resultTitle}>🎉 Congratulations!</p>
            <p style={styles.resultOffer}>{offer.label}</p>
            <p style={styles.resultDescription}>
              This exclusive offer is waiting for you at checkout. Sign up now to claim it!
            </p>
            <button onClick={handleContinue} style={styles.continueButton}>
              Claim Your Offer
            </button>
          </div>
        ) : (
          <p style={styles.spinHint}>Click the button above to spin and reveal your offer</p>
        )}
      </div>

      <div style={styles.links}>
        <Link to="/signup" style={styles.link}>Go to Sign Up</Link>
        <Link to="/login" style={styles.link}>Already a member? Log In</Link>
      </div>
    </div>
  );
}

const styles = {
  wheelCard: {
    ...componentStyles.card,
    marginTop: theme.spacing['2xl'],
    textAlign: "center",
  },
  wheelContainer: {
    position: "relative",
    width: 300,
    height: 300,
    margin: `${theme.spacing['2xl']}px auto`,
  },
  wheelVisual: {
    position: "absolute",
    width: 300,
    height: 300,
    borderRadius: "50%",
    background: `linear-gradient(135deg, ${theme.colors.primary} 0%, ${theme.colors.primaryLight} 100%)`,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    boxShadow: theme.shadows.lg,
    border: `4px solid ${theme.colors.primaryDark}`,
  },
  offerSlice: {
    position: "absolute",
    width: "100%",
    height: "100%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: theme.fonts.sizes.sm,
    fontWeight: theme.fonts.weights.bold,
    color: "#fff",
  },
  offerLabel: {
    textAlign: "center",
    wordBreak: "break-word",
  },
  pointer: {
    position: "absolute",
    top: -15,
    left: "50%",
    transform: "translateX(-50%)",
    width: 0,
    height: 0,
    borderLeft: "12px solid transparent",
    borderRight: "12px solid transparent",
    borderTop: `20px solid ${theme.colors.warning}`,
    zIndex: 10,
  },
  spinButton: {
    ...componentStyles.button,
    ...componentStyles.buttonPrimary,
    fontSize: theme.fonts.sizes.lg,
    padding: `${theme.spacing.lg}px ${theme.spacing['2xl']}px`,
    marginBottom: theme.spacing.xl,
  },
  resultBox: {
    marginTop: theme.spacing.xl,
    padding: theme.spacing.xl,
    borderRadius: theme.radius.lg,
    background: `linear-gradient(135deg, ${theme.colors.success}10 0%, ${theme.colors.primaryLight}10 100%)`,
    border: `2px solid ${theme.colors.success}`,
  },
  resultTitle: {
    margin: 0,
    fontSize: theme.fonts.sizes.xl,
    fontWeight: theme.fonts.weights.bold,
    color: theme.colors.primaryDark,
  },
  resultOffer: {
    margin: `${theme.spacing.md}px 0`,
    fontSize: "2rem",
    fontWeight: theme.fonts.weights.bold,
    background: `linear-gradient(135deg, ${theme.colors.primary}, ${theme.colors.primaryLight})`,
    WebkitBackgroundClip: "text",
    WebkitTextFillColor: "transparent",
    backgroundClip: "text",
  },
  resultDescription: {
    margin: `${theme.spacing.md}px 0 ${theme.spacing.lg}px`,
    color: theme.colors.text.secondary,
    fontSize: theme.fonts.sizes.base,
  },
  continueButton: {
    ...componentStyles.button,
    ...componentStyles.buttonPrimary,
    fontSize: theme.fonts.sizes.base,
  },
  spinHint: {
    marginTop: theme.spacing.lg,
    color: theme.colors.text.tertiary,
    fontSize: theme.fonts.sizes.sm,
  },
  links: {
    marginTop: theme.spacing['2xl'],
    display: "flex",
    gap: theme.spacing.lg,
    justifyContent: "center",
    flexWrap: "wrap",
  },
  link: {
    ...componentStyles.link,
    padding: `${theme.spacing.md}px ${theme.spacing.lg}px`,
    borderRadius: theme.radius.lg,
    border: `1px solid ${theme.colors.accent}`,
  },
};
