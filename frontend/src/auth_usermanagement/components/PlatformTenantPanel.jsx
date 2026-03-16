import { useEffect, useMemo, useState } from "react";

import { getPlatformTenants, suspendPlatformTenant, unsuspendPlatformTenant } from "../services/authApi";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "./Toast";
import { ConfirmDialog } from "./ConfirmDialog";
import { getErrorMessage, getSuccessMessage } from "../utils/errorHandling";

export function PlatformTenantPanel() {
  const { token } = useAuth();
  const toast = useToast();

  const [tenants, setTenants] = useState([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [isLoading, setIsLoading] = useState(false);
  const [processingTenantId, setProcessingTenantId] = useState(null);
  const [confirmDialog, setConfirmDialog] = useState({ isOpen: false, action: null, tenant: null });

  const loadTenants = async () => {
    if (!token) {
      setTenants([]);
      return;
    }

    setIsLoading(true);
    try {
      const response = await getPlatformTenants(token);
      setTenants(response);
    } catch (err) {
      toast.error(getErrorMessage("load_tenants", err));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadTenants();
  }, [token]);

  const filteredTenants = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();
    return tenants.filter((tenant) => {
      const matchesSearch = normalizedSearch.length === 0 || tenant.name.toLowerCase().includes(normalizedSearch);
      const matchesStatus = statusFilter === "all" || tenant.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [searchTerm, statusFilter, tenants]);

  const summary = useMemo(() => ({
    total: tenants.length,
    active: tenants.filter((tenant) => tenant.status === "active").length,
    suspended: tenants.filter((tenant) => tenant.status === "suspended").length,
  }), [tenants]);

  const openConfirm = (action, tenant) => {
    setConfirmDialog({
      isOpen: true,
      action,
      tenant,
    });
  };

  const handleConfirm = async () => {
    const { action, tenant } = confirmDialog;
    setConfirmDialog({ isOpen: false, action: null, tenant: null });

    if (!tenant) {
      return;
    }

    setProcessingTenantId(tenant.tenant_id);
    try {
      if (action === "suspend") {
        await suspendPlatformTenant(token, tenant.tenant_id);
        toast.success(getSuccessMessage("suspend_tenant", { name: tenant.name }));
      } else {
        await unsuspendPlatformTenant(token, tenant.tenant_id);
        toast.success(getSuccessMessage("unsuspend_tenant", { name: tenant.name }));
      }
      await loadTenants();
    } catch (err) {
      toast.error(getErrorMessage(`${action}_tenant`, err, { name: tenant.name }));
    } finally {
      setProcessingTenantId(null);
    }
  };

  return (
    <section style={{
      background: "linear-gradient(135deg, #f8fbfd 0%, #eef5f9 100%)",
      border: "1px solid #d7e3ea",
      borderRadius: "16px",
      padding: "22px",
      boxShadow: "0 12px 30px rgba(15, 56, 67, 0.08)",
      display: "grid",
      gap: "18px"
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: "12px", alignItems: "center", flexWrap: "wrap" }}>
        <div>
          <div style={{ display: "inline-flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
            <span style={eyebrowStyle}>Platform Tenants</span>
            <span style={subtleBadgeStyle}>{summary.total} organizations</span>
          </div>
          <h3 style={{ margin: 0, fontSize: "22px", color: "#16313d", letterSpacing: "-0.02em" }}>Tenant Operations</h3>
          <p style={{ margin: "6px 0 0", color: "#5b7280", fontSize: "14px", maxWidth: "720px", lineHeight: 1.5 }}>
            Review tenant health, search organizations quickly, and suspend or restore access without leaving the superadmin workspace.
          </p>
        </div>
        <button onClick={loadTenants} disabled={isLoading} style={refreshButtonStyle}>
          {isLoading ? "Loading..." : "Refresh"}
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "12px" }}>
        <div style={summaryCardStyle}>
          <span style={summaryLabelStyle}>Total</span>
          <strong style={summaryValueStyle}>{summary.total}</strong>
        </div>
        <div style={summaryCardStyle}>
          <span style={summaryLabelStyle}>Active</span>
          <strong style={{ ...summaryValueStyle, color: "#1f6b3b" }}>{summary.active}</strong>
        </div>
        <div style={summaryCardStyle}>
          <span style={summaryLabelStyle}>Suspended</span>
          <strong style={{ ...summaryValueStyle, color: "#b42318" }}>{summary.suspended}</strong>
        </div>
      </div>

      <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" }}>
        <input
          type="text"
          value={searchTerm}
          onChange={(event) => setSearchTerm(event.target.value)}
          placeholder="Search tenants"
          aria-label="Search tenants"
          style={searchInputStyle}
        />
        <select
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value)}
          aria-label="Filter tenants by status"
          style={filterSelectStyle}
        >
          <option value="all">All Statuses</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
        </select>
      </div>

      <div style={{
        display: "grid",
        gridAutoFlow: "column",
        gridAutoColumns: "minmax(280px, 1fr)",
        gap: "14px",
        overflowX: "auto",
        paddingBottom: "4px"
      }}>
        {filteredTenants.map((tenant) => {
          const isProcessing = processingTenantId === tenant.tenant_id;
          return (
            <article
              key={tenant.tenant_id}
              style={{
                border: "1px solid #d5e1e8",
                backgroundColor: "rgba(255, 255, 255, 0.92)",
                borderRadius: "14px",
                padding: "16px",
                display: "grid",
                minHeight: "188px",
                gap: "12px",
                opacity: isProcessing ? 0.65 : 1,
                boxShadow: "0 10px 24px rgba(23, 49, 61, 0.06)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: "12px", alignItems: "flex-start", flexWrap: "wrap" }}>
                <div>
                  <div style={{ fontWeight: 700, color: "#17313d", fontSize: "16px", letterSpacing: "-0.01em" }}>{tenant.name}</div>
                  <div style={{ color: "#6b778c", fontSize: "13px", marginTop: "4px" }}>
                    {tenant.plan} plan • created {new Date(tenant.created_at).toLocaleDateString()}
                  </div>
                </div>
                <span style={badgeStyle(tenant.status === "active" ? "#edf8ef" : "#fff1f0", tenant.status === "active" ? "#256f3a" : "#b42318")}>
                  {tenant.status}
                </span>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "10px" }}>
                <div style={statTileStyle}>
                  <span style={statTileLabelStyle}>Members</span>
                  <strong style={statTileValueStyle}>{tenant.member_count}</strong>
                </div>
                <div style={statTileStyle}>
                  <span style={statTileLabelStyle}>Owners</span>
                  <strong style={statTileValueStyle}>{tenant.owner_count}</strong>
                </div>
              </div>

              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginTop: "auto" }}>
                {tenant.status === "active" ? (
                  <button disabled={isProcessing} onClick={() => openConfirm("suspend", tenant)} style={dangerActionStyle}>
                    {isProcessing ? "Processing..." : "Suspend Tenant"}
                  </button>
                ) : (
                  <button disabled={isProcessing} onClick={() => openConfirm("unsuspend", tenant)} style={primaryActionStyle}>
                    {isProcessing ? "Processing..." : "Unsuspend Tenant"}
                  </button>
                )}
              </div>
            </article>
          );
        })}

        {!isLoading && filteredTenants.length === 0 ? (
          <div style={{ padding: "24px", textAlign: "center", color: "#6b778c" }}>
            No tenants match the current filters.
          </div>
        ) : null}
      </div>

      <ConfirmDialog
        isOpen={confirmDialog.isOpen}
        title={confirmDialog.action === "suspend" ? "Suspend Tenant" : "Unsuspend Tenant"}
        message={confirmDialog.tenant
          ? confirmDialog.action === "suspend"
            ? `Suspend ${confirmDialog.tenant.name}? Tenant-scoped activity will be blocked until restored.`
            : `Unsuspend ${confirmDialog.tenant.name}? Tenant-scoped activity will be restored.`
          : ""}
        confirmText={confirmDialog.action === "suspend" ? "Suspend" : "Unsuspend"}
        cancelText="Cancel"
        variant={confirmDialog.action === "suspend" ? "danger" : "warning"}
        onConfirm={handleConfirm}
        onCancel={() => setConfirmDialog({ isOpen: false, action: null, tenant: null })}
      />
    </section>
  );
}

function badgeStyle(backgroundColor, color) {
  return {
    display: "inline-flex",
    alignItems: "center",
    gap: "6px",
    backgroundColor,
    color,
    borderRadius: "999px",
    padding: "4px 10px",
    fontSize: "12px",
    fontWeight: 600,
  };
}

const eyebrowStyle = {
  display: "inline-flex",
  alignItems: "center",
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  fontSize: "11px",
  fontWeight: 700,
  color: "#0f5f73",
};

const subtleBadgeStyle = {
  display: "inline-flex",
  alignItems: "center",
  borderRadius: "999px",
  backgroundColor: "#dfeff4",
  color: "#36505c",
  padding: "4px 10px",
  fontSize: "12px",
  fontWeight: 600,
};

const refreshButtonStyle = {
  border: "1px solid #b5c8d1",
  backgroundColor: "#ffffff",
  color: "#17313d",
  borderRadius: "10px",
  padding: "10px 14px",
  fontWeight: 600,
  cursor: "pointer",
  boxShadow: "0 1px 2px rgba(23, 49, 61, 0.06)",
};

const summaryCardStyle = {
  backgroundColor: "rgba(255, 255, 255, 0.8)",
  border: "1px solid #d7e3ea",
  borderRadius: "12px",
  padding: "14px 16px",
  display: "grid",
  gap: "6px",
};

const summaryLabelStyle = {
  color: "#627885",
  fontSize: "12px",
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.06em",
};

const summaryValueStyle = {
  color: "#17313d",
  fontSize: "28px",
  lineHeight: 1,
  letterSpacing: "-0.03em",
};

const searchInputStyle = {
  padding: "11px 14px",
  minWidth: 260,
  flex: "1 1 260px",
  borderRadius: "10px",
  border: "1px solid #c6d6de",
  backgroundColor: "#fff",
  color: "#17313d",
};

const filterSelectStyle = {
  padding: "11px 14px",
  borderRadius: "10px",
  border: "1px solid #c6d6de",
  backgroundColor: "#fff",
  color: "#17313d",
};

const statTileStyle = {
  borderRadius: "12px",
  backgroundColor: "#f6fafc",
  border: "1px solid #e2ebf0",
  padding: "12px",
  display: "grid",
  gap: "4px",
};

const statTileLabelStyle = {
  color: "#647986",
  fontSize: "11px",
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: "0.06em",
};

const statTileValueStyle = {
  color: "#17313d",
  fontSize: "22px",
  lineHeight: 1,
};

const primaryActionStyle = {
  border: "none",
  borderRadius: "10px",
  padding: "10px 14px",
  backgroundColor: "#0f766e",
  color: "#fff",
  fontWeight: 600,
  cursor: "pointer",
};

const dangerActionStyle = {
  border: "none",
  borderRadius: "10px",
  padding: "10px 14px",
  backgroundColor: "#b42318",
  color: "#fff",
  fontWeight: 600,
  cursor: "pointer",
};