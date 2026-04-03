import { getFunnelContext } from "../state/funnelContext";

export function FunnelBanner() {
  const context = getFunnelContext();
  if (!context) {
    return null;
  }

  return (
    <div style={styles.wrap}>
      <strong>Journey Context:</strong>
      <span style={styles.item}>Splash: {context.splashId || "-"}</span>
      <span style={styles.item}>Module: {context.moduleTarget || "-"}</span>
      <span style={styles.item}>Offer: {context.offer?.label || "Not selected"}</span>
    </div>
  );
}

const styles = {
  wrap: {
    marginBottom: 16,
    padding: "10px 12px",
    borderRadius: 10,
    background: "#eef8f5",
    border: "1px solid #bfded3",
    color: "#1e4f44",
    display: "flex",
    flexWrap: "wrap",
    gap: 12,
    fontSize: 14,
  },
  item: {
    fontWeight: 600,
  },
};
