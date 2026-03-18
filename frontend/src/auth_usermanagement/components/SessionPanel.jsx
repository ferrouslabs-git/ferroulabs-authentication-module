import { useEffect, useState } from "react";
import { listSessions, revokeSession } from "../services/authApi";
import { useAuth } from "../hooks/useAuth";

export function SessionPanel() {
  const { token, sessionId } = useAuth();
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadSessions = async () => {
    if (!token) {
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await listSessions(token, sessionId, true);
      setSessions(Array.isArray(data) ? data : []);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(detail || "Failed to load sessions.");
    } finally {
      setLoading(false);
    }
  };

  const handleRevoke = async (targetSessionId, isCurrent) => {
    if (!token || isCurrent) {
      return;
    }
    try {
      await revokeSession(token, targetSessionId);
      await loadSessions();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(detail || "Failed to revoke session.");
    }
  };

  useEffect(() => {
    loadSessions();
  }, [token, sessionId]);

  return (
    <div style={{
      backgroundColor: "white",
      borderRadius: "8px",
      padding: "20px",
      boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
        <h2 style={{ margin: 0, fontSize: "20px", color: "#333" }}>Device Sessions</h2>
        <button
          type="button"
          onClick={loadSessions}
          disabled={loading}
          style={{
            border: "1px solid #1976d2",
            color: "#1976d2",
            backgroundColor: "#fff",
            borderRadius: "6px",
            padding: "6px 10px",
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          Refresh
        </button>
      </div>

      {error ? <p style={{ color: "#c62828" }}>{error}</p> : null}
      {loading ? <p style={{ color: "#666" }}>Loading sessions...</p> : null}

      {!loading && sessions.length === 0 ? (
        <p style={{ color: "#666" }}>No sessions found.</p>
      ) : (
        <div style={{ display: "grid", gap: "10px" }}>
          {sessions.map((s) => (
            <div
              key={s.session_id}
              style={{
                border: "1px solid #e0e0e0",
                borderRadius: "8px",
                padding: "10px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                gap: "10px",
              }}
            >
              <div>
                <div style={{ fontWeight: 600, color: "#333" }}>
                  {s.device_info || "Unknown device"} {s.is_current ? "(Current)" : ""}
                </div>
                <div style={{ fontSize: "12px", color: "#666" }}>
                  IP: {s.ip_address || "unknown"} | Created: {new Date(s.created_at).toLocaleString()}
                </div>
                <div style={{ fontSize: "12px", color: "#666" }}>
                  {s.revoked_at ? `Revoked: ${new Date(s.revoked_at).toLocaleString()}` : "Active"}
                </div>
              </div>
              <button
                type="button"
                disabled={s.is_current || s.is_revoked}
                onClick={() => handleRevoke(s.session_id, s.is_current)}
                style={{
                  border: "none",
                  borderRadius: "6px",
                  padding: "8px 12px",
                  backgroundColor: s.is_current || s.is_revoked ? "#ddd" : "#d32f2f",
                  color: "white",
                  cursor: s.is_current || s.is_revoked ? "not-allowed" : "pointer",
                }}
              >
                {s.is_revoked ? "Revoked" : "Revoke"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}