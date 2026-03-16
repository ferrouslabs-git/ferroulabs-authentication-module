import { useEffect, useMemo, useState } from "react";
import {
  demotePlatformUser,
  getPlatformUsers,
  getTenantUsers,
  promotePlatformUser,
  updateTenantUserRole,
  removeTenantUser,
  suspendUser,
  unsuspendUser,
} from "../services/authApi";
import { useAuth } from "../hooks/useAuth";
import { useRole } from "../hooks/useRole";
import { RoleSelector } from "./RoleSelector";
import { ConfirmDialog } from "./ConfirmDialog";
import { useToast } from "./Toast";
import { PERMISSIONS, checkPermission } from "../constants/permissions";
import { getErrorMessage, getSuccessMessage } from "../utils/errorHandling";

export function UserList({ className, canManage: canManageProp, mode = "tenant", missingTenantMessage = "Select a tenant to view users." }) {
  const { token, tenantId, user: currentUser } = useAuth();
  const { role } = useRole();
  const toast = useToast();

  const [users, setUsers] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [processingUserId, setProcessingUserId] = useState(null);
  const [confirmDialog, setConfirmDialog] = useState({ isOpen: false, action: null, user: null });
  const [lastFailedOperation, setLastFailedOperation] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortConfig, setSortConfig] = useState({ key: "email", direction: "asc" });
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768);

  const isPlatformAdmin = currentUser?.is_platform_admin || false;
  const isPlatformView = mode === "platform";

  const canManage = canManageProp !== undefined
    ? canManageProp
    : checkPermission(currentUser, PERMISSIONS.REMOVE_USERS, role);
  const canSuspendUsers = checkPermission(currentUser, PERMISSIONS.SUSPEND_USERS, role);
  const canRemoveUsers = canManage && !isPlatformView;

  const canEditRoleForUser = (targetUser) => {
    if (isPlatformView) return false;
    if (!canManage || !targetUser) return false;
    if (isPlatformAdmin) return true;
    if (role === "owner") return true;
    if (role === "admin") {
      return targetUser.role !== "owner";
    }
    return false;
  };

  const getRoleOptionsForUser = (targetUser) => {
    if (isPlatformView) return [];
    if (!targetUser) return ["viewer", "member"];
    if (isPlatformAdmin || role === "owner") {
      return ["viewer", "member", "admin", "owner"];
    }
    if (role === "admin") {
      return ["viewer", "member"];
    }
    return [targetUser.role];
  };

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const loadUsers = async () => {
    if (!token || (!isPlatformView && !tenantId)) {
      setUsers([]);
      return;
    }

    setIsLoading(true);
    try {
      const response = isPlatformView
        ? await getPlatformUsers(token)
        : await getTenantUsers(token, tenantId);
      setUsers(response);
    } catch (err) {
      toast.error(getErrorMessage("load_users", err));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, [token, tenantId, mode]);

  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, roleFilter, statusFilter, pageSize, mode]);

  const visibleUsers = useMemo(() => {
    const filtered = users.filter((user) => {
      const normalizedSearch = searchTerm.trim().toLowerCase();
      const matchesSearch =
        normalizedSearch.length === 0 ||
        user.email?.toLowerCase().includes(normalizedSearch) ||
        (user.name || "").toLowerCase().includes(normalizedSearch) ||
        (isPlatformView && (user.memberships || []).some((membership) =>
          membership.tenant_name?.toLowerCase().includes(normalizedSearch)
        ));

      const matchesRole = roleFilter === "all" || (
        isPlatformView
          ? roleFilter === "super_admin"
            ? Boolean(user.is_platform_admin)
            : roleFilter === "no_membership"
              ? (user.memberships || []).length === 0
              : (user.memberships || []).some((membership) => membership.role === roleFilter)
          : user.role === roleFilter
      );

      const accountStatus = user.is_active === false ? "suspended" : "active";
      const matchesStatus = statusFilter === "all" || accountStatus === statusFilter;

      return matchesSearch && matchesRole && matchesStatus;
    });

    const getSortValue = (user, key) => {
      if (key === "role") {
        if (!isPlatformView) {
          return user.role ?? "";
        }
        if (user.is_platform_admin) {
          return "super_admin";
        }
        return (user.memberships || []).map((membership) => membership.role).sort().join(",");
      }

      if (key === "status") {
        return user.is_active === false ? "suspended" : "active";
      }

      return user[key] ?? "";
    };

    return [...filtered].sort((a, b) => {
      const aValue = getSortValue(a, sortConfig.key).toString().toLowerCase();
      const bValue = getSortValue(b, sortConfig.key).toString().toLowerCase();

      if (aValue < bValue) return sortConfig.direction === "asc" ? -1 : 1;
      if (aValue > bValue) return sortConfig.direction === "asc" ? 1 : -1;
      return 0;
    });
  }, [users, searchTerm, roleFilter, statusFilter, sortConfig, isPlatformView]);

  const totalPages = Math.max(1, Math.ceil(visibleUsers.length / pageSize));
  const clampedPage = Math.min(currentPage, totalPages);
  const startIndex = (clampedPage - 1) * pageSize;
  const paginatedUsers = visibleUsers.slice(startIndex, startIndex + pageSize);

  const platformSummary = useMemo(() => ({
    total: users.length,
    superAdmins: users.filter((user) => user.is_platform_admin).length,
    suspended: users.filter((user) => user.is_active === false).length,
    noMembership: users.filter((user) => (user.memberships || []).length === 0).length,
  }), [users]);

  const setSort = (key) => {
    setSortConfig((prev) => {
      if (prev.key === key) {
        return { key, direction: prev.direction === "asc" ? "desc" : "asc" };
      }
      return { key, direction: "asc" };
    });
  };

  const getAriaSort = (key) => {
    if (sortConfig.key !== key) return "none";
    return sortConfig.direction === "asc" ? "ascending" : "descending";
  };

  const formatLastLogin = (user) => {
    const raw = user.last_login || user.last_seen_at || user.updated_at || null;
    if (!raw) {
      return "-";
    }
    const dt = new Date(raw);
    if (Number.isNaN(dt.getTime())) {
      return "-";
    }
    return dt.toLocaleString();
  };

  const formatMembershipSummary = (user) => {
    if (!isPlatformView) {
      return user.role;
    }
    if (!user.memberships || user.memberships.length === 0) {
      return "No tenant memberships";
    }
    return user.memberships
      .map((membership) => `${membership.tenant_name} (${membership.role})`)
      .join(", ");
  };

  const tenantCount = (user) => (user.memberships || []).length;

  const applyPlatformFilter = (nextFilter) => {
    setRoleFilter(nextFilter);
  };

  const handleRoleChange = async (userId, nextRole) => {
    const user = users.find((candidate) => candidate.user_id === userId);
    setProcessingUserId(userId);

    try {
      await updateTenantUserRole(token, tenantId, userId, nextRole);
      toast.success(`Updated ${user?.email}'s role to ${nextRole}`);
      await loadUsers();
    } catch (err) {
      toast.error(getErrorMessage("update_role", err, { email: user?.email }));
    } finally {
      setProcessingUserId(null);
    }
  };

  const confirmRemove = (user) => {
    setConfirmDialog({
      isOpen: true,
      action: "remove",
      user,
      title: "Remove User",
      message: `Are you sure you want to remove ${user.email} from this tenant? They will lose access immediately.`,
    });
  };

  const confirmSuspend = (user) => {
    setConfirmDialog({
      isOpen: true,
      action: "suspend",
      user,
      title: "Suspend User",
      message: `Are you sure you want to suspend ${user.email}? They will be unable to log in until unsuspended.`,
    });
  };

  const confirmUnsuspend = (user) => {
    setConfirmDialog({
      isOpen: true,
      action: "unsuspend",
      user,
      title: "Unsuspend User",
      message: `Are you sure you want to unsuspend ${user.email}? They will regain access immediately.`,
    });
  };

  const confirmPromote = (user) => {
    setConfirmDialog({
      isOpen: true,
      action: "promote",
      user,
      title: "Grant Super Admin",
      message: `Grant super admin access to ${user.email}? They will gain platform-wide control.`,
    });
  };

  const confirmDemote = (user) => {
    setConfirmDialog({
      isOpen: true,
      action: "demote",
      user,
      title: "Remove Super Admin",
      message: `Remove super admin access from ${user.email}? They will lose platform-wide control immediately.`,
    });
  };

  const executeAction = async (action, user) => {
    if (!user) return;

    setProcessingUserId(user.user_id);
    setLastFailedOperation(null);

    try {
      if (action === "remove") {
        await removeTenantUser(token, tenantId, user.user_id);
        toast.success(getSuccessMessage("remove_user", { email: user.email }));
      } else if (action === "promote") {
        await promotePlatformUser(token, user.user_id);
        toast.success(getSuccessMessage("promote_super_admin", { email: user.email }));
      } else if (action === "demote") {
        await demotePlatformUser(token, user.user_id);
        toast.success(getSuccessMessage("demote_super_admin", { email: user.email }));
      } else if (action === "suspend") {
        await suspendUser(token, tenantId, user.user_id);
        toast.success(getSuccessMessage("suspend_user", { email: user.email }));
      } else if (action === "unsuspend") {
        await unsuspendUser(token, tenantId, user.user_id);
        toast.success(getSuccessMessage("unsuspend_user", { email: user.email }));
      }
      await loadUsers();
    } catch (err) {
      const errorMsg = getErrorMessage(`${action}_user`, err, { email: user.email });
      toast.error(errorMsg);
      setLastFailedOperation({ action, user, errorMsg });
    } finally {
      setProcessingUserId(null);
    }
  };

  const handleConfirm = async () => {
    const { action, user } = confirmDialog;
    setConfirmDialog({ isOpen: false, action: null, user: null });
    await executeAction(action, user);
  };

  const handleRetry = async () => {
    if (!lastFailedOperation) {
      return;
    }

    const { action, user } = lastFailedOperation;
    setLastFailedOperation(null);
    await executeAction(action, user);
  };

  const handleCancel = () => {
    setConfirmDialog({ isOpen: false, action: null, user: null });
  };

  const title = isPlatformView ? "All Platform Users" : "Tenant Users";
  const subtitle = isPlatformView
    ? "Manage global access, account state, and organization membership from one directory."
    : "Review tenant memberships, update roles, and remove organization access when needed.";
  const resultCountLabel = visibleUsers.length === 1 ? "1 matching account" : `${visibleUsers.length} matching accounts`;

  return (
    <div className={className} style={getPanelShellStyle(isPlatformView)}>
      {!tenantId && !isPlatformView ? (
        <div
          style={{
            padding: "12px 14px",
            border: "1px solid #ffe0b2",
            borderRadius: "6px",
            backgroundColor: "#fff8ee",
            color: "#7a4f1e",
            marginBottom: "12px",
          }}
        >
          {missingTenantMessage}
        </div>
      ) : null}

      {lastFailedOperation ? (
        <div style={{
          background: "linear-gradient(135deg, #fff7df 0%, #fff0c2 100%)",
          border: "1px solid rgba(196, 139, 0, 0.28)",
          borderRadius: "16px",
          padding: "14px 16px",
          marginBottom: "18px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "12px",
          boxShadow: "0 10px 24px rgba(139, 101, 8, 0.08)"
        }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, color: "#6f4a00", marginBottom: "4px", letterSpacing: "0.01em" }}>
              Operation Failed
            </div>
            <div style={{ fontSize: "14px", color: "#6f4a00" }}>
              {lastFailedOperation.errorMsg} ({lastFailedOperation.action} {lastFailedOperation.user.email})
            </div>
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              onClick={handleRetry}
              style={getActionButtonStyle("warning")}
            >
              Retry
            </button>
            <button
              onClick={() => setLastFailedOperation(null)}
              style={getActionButtonStyle("ghost")}
            >
              Dismiss
            </button>
          </div>
        </div>
      ) : null}

      <div style={headerShellStyle}>
        <div>
          <div style={eyebrowStyle}>{isPlatformView ? "Platform Directory" : "Tenant Directory"}</div>
          <div style={headerTitleRowStyle}>
            <h3 style={headerTitleStyle}>{title}</h3>
            <span style={headerCountBadgeStyle}>{resultCountLabel}</span>
          </div>
          <p style={headerSubtitleStyle}>{subtitle}</p>
        </div>
        <button onClick={loadUsers} disabled={isLoading} aria-label="Refresh user list" style={getActionButtonStyle("primary")}>
          {isLoading ? "Loading..." : "Refresh"}
        </button>
      </div>

      {isPlatformView ? (
        <div style={quickFilterStripStyle}>
          <button type="button" onClick={() => applyPlatformFilter("all")} style={getQuickFilterButtonStyle(roleFilter === "all", "neutral")}>
            <span>All Users</span>
            <strong>{platformSummary.total}</strong>
          </button>
          <button type="button" onClick={() => applyPlatformFilter("super_admin")} style={getQuickFilterButtonStyle(roleFilter === "super_admin", "accent")}>
            <span>Super Admins</span>
            <strong>{platformSummary.superAdmins}</strong>
          </button>
          <button type="button" onClick={() => setStatusFilter(statusFilter === "suspended" ? "all" : "suspended")} style={getQuickFilterButtonStyle(statusFilter === "suspended", "danger")}>
            <span>Suspended</span>
            <strong>{platformSummary.suspended}</strong>
          </button>
          <button type="button" onClick={() => applyPlatformFilter("no_membership")} style={getQuickFilterButtonStyle(roleFilter === "no_membership", "warm")}>
            <span>No Membership</span>
            <strong>{platformSummary.noMembership}</strong>
          </button>
        </div>
      ) : null}

      <div style={toolbarShellStyle}>
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder={isPlatformView ? "Search by email, name, or tenant" : "Search by email or name"}
          aria-label="Search users"
          style={{ ...controlStyle, minWidth: 220, flex: "1 1 260px" }}
        />
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          aria-label="Filter users by role"
          style={controlStyle}
        >
          <option value="all">All Roles</option>
          {isPlatformView ? <option value="super_admin">Super Admin</option> : null}
          <option value="owner">Owner</option>
          <option value="admin">Admin</option>
          <option value="member">Member</option>
          <option value="viewer">Viewer</option>
          {isPlatformView ? <option value="no_membership">No Tenant Membership</option> : null}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          aria-label="Filter users by account status"
          style={controlStyle}
        >
          <option value="all">All Statuses</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
        </select>
        <select
          value={String(pageSize)}
          onChange={(e) => setPageSize(Number(e.target.value))}
          aria-label="Users per page"
          style={controlStyle}
        >
          <option value="10">10 / page</option>
          <option value="25">25 / page</option>
          <option value="50">50 / page</option>
        </select>
      </div>

      {isLoading && users.length === 0 ? (
        <div style={emptyStateStyle}>
          <div style={{ fontSize: "14px" }}>Loading users...</div>
        </div>
      ) : null}

      {!isLoading && users.length === 0 && (isPlatformView || tenantId) ? (
        <div style={emptyStateStyle}>
          <div style={{ fontSize: "14px" }}>
            {isPlatformView ? "No users found in this platform." : "No users found in this tenant."}
          </div>
        </div>
      ) : null}

      {paginatedUsers.length > 0 ? (
        isMobile ? (
          <div role="list" aria-label={isPlatformView ? "Platform users" : "Tenant users"} style={{ display: "grid", gap: 10 }}>
            {paginatedUsers.map((user) => {
              const isProcessing = processingUserId === user.user_id;
              const isCurrentUser = user.user_id === currentUser?.id;
              const canEditRole = canEditRoleForUser(user) && !isCurrentUser;

              return (
                <article
                  key={user.user_id}
                  role="listitem"
                  aria-label={`User ${user.email}`}
                  style={{
                    border: "1px solid rgba(16, 24, 40, 0.08)",
                    borderRadius: 18,
                    padding: 14,
                    opacity: isProcessing ? 0.6 : 1,
                    background: "linear-gradient(180deg, #ffffff 0%, #fbfcfe 100%)",
                    boxShadow: "0 12px 32px rgba(15, 23, 42, 0.08)"
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 10 }}>
                    <div>
                      <div style={mobileUserEmailStyle}>{user.email}</div>
                      <div style={mobileUserNameStyle}>{user.name || "No display name"}</div>
                    </div>
                    {isPlatformView ? (
                      <span style={getStatusBadgeStyle(user.is_platform_admin ? "accent" : "neutral")}>
                        {user.is_platform_admin ? "Super Admin" : "Tenant User"}
                      </span>
                    ) : null}
                  </div>
                  {isPlatformView ? (
                    <>
                      <div style={mobileMetaRowStyle}><strong>Tenants</strong> <span style={countBadgeStyle}>{tenantCount(user)}</span></div>
                      <div style={mobileMetaRowStyle}><strong>Memberships</strong> <span>{formatMembershipSummary(user)}</span></div>
                    </>
                  ) : (
                    <>
                      <div style={mobileMetaRowStyle}>
                        <strong>Role</strong>
                        {canEditRole ? (
                          <RoleSelector
                            value={user.role}
                            onChange={(nextRole) => handleRoleChange(user.user_id, nextRole)}
                            disabled={isProcessing}
                            options={getRoleOptionsForUser(user)}
                          />
                        ) : (
                          user.role
                        )}
                      </div>
                      <div style={mobileMetaRowStyle}><strong>Status</strong> <span>{user.status}</span></div>
                    </>
                  )}
                  <div style={mobileMetaRowStyle}><strong>Last Login</strong> <span>{formatLastLogin(user)}</span></div>
                  {isPlatformAdmin ? (
                    <div style={mobileMetaRowStyle}>
                      <strong>Account</strong>
                      <span style={getStatusBadgeStyle(user.is_active ? "success" : "danger")}>
                        {user.is_active ? "Active" : "Suspended"}
                      </span>
                    </div>
                  ) : null}
                  {canManage || isPlatformAdmin ? (
                    <div style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap" }}>
                      {canRemoveUsers && !isCurrentUser ? (
                        <button
                          onClick={() => confirmRemove(user)}
                          aria-label={`Remove ${user.email}`}
                          disabled={isProcessing}
                          style={getActionButtonStyle("danger")}
                        >
                          Remove
                        </button>
                      ) : null}
                      {isPlatformAdmin && canSuspendUsers && !isCurrentUser ? (
                        user.is_platform_admin ? (
                          <button
                            onClick={() => confirmDemote(user)}
                            aria-label={`Remove super admin from ${user.email}`}
                            disabled={isProcessing}
                            style={getActionButtonStyle("ghost")}
                          >
                            {isProcessing ? "Processing..." : "Remove Super Admin"}
                          </button>
                        ) : (
                          <button
                            onClick={() => confirmPromote(user)}
                            aria-label={`Grant super admin to ${user.email}`}
                            disabled={isProcessing}
                            style={getActionButtonStyle("primary")}
                          >
                            {isProcessing ? "Processing..." : "Grant Super Admin"}
                          </button>
                        )
                      ) : null}
                      {isPlatformAdmin && canSuspendUsers && !isCurrentUser ? (
                        user.is_active ? (
                          <button
                            onClick={() => confirmSuspend(user)}
                            aria-label={`Suspend ${user.email}`}
                            disabled={isProcessing}
                            style={getActionButtonStyle("danger")}
                          >
                            {isProcessing ? "Processing..." : "Suspend"}
                          </button>
                        ) : (
                          <button
                            onClick={() => confirmUnsuspend(user)}
                            aria-label={`Unsuspend ${user.email}`}
                            disabled={isProcessing}
                            style={getActionButtonStyle("secondary")}
                          >
                            {isProcessing ? "Processing..." : "Unsuspend"}
                          </button>
                        )
                      ) : null}
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        ) : (
          <div style={tableShellStyle}>
            <table style={tableStyle}>
              <caption style={tableCaptionStyle}>
                Showing {paginatedUsers.length} of {visibleUsers.length} filtered users
              </caption>
              <thead>
                <tr>
                  <th style={tableHeaderCellStyle} align="left" aria-sort={getAriaSort("email")}>
                    <button onClick={() => setSort("email")} aria-label="Sort by email" style={sortButtonStyle}>
                      Email {sortConfig.key === "email" ? (sortConfig.direction === "asc" ? "▲" : "▼") : ""}
                    </button>
                  </th>
                  <th style={tableHeaderCellStyle} align="left" aria-sort={getAriaSort("name")}>
                    <button onClick={() => setSort("name")} aria-label="Sort by name" style={sortButtonStyle}>
                      Name {sortConfig.key === "name" ? (sortConfig.direction === "asc" ? "▲" : "▼") : ""}
                    </button>
                  </th>
                  <th style={tableHeaderCellStyle} align="left" aria-sort={getAriaSort("role")}>
                    <button onClick={() => setSort("role")} aria-label={isPlatformView ? "Sort by memberships" : "Sort by role"} style={sortButtonStyle}>
                      {isPlatformView ? "Memberships" : "Role"} {sortConfig.key === "role" ? (sortConfig.direction === "asc" ? "▲" : "▼") : ""}
                    </button>
                  </th>
                  <th style={tableHeaderCellStyle} align="left">{isPlatformView ? "Platform Access" : "Status"}</th>
                  <th style={tableHeaderCellStyle} align="left">Last Login</th>
                  {isPlatformAdmin ? <th style={tableHeaderCellStyle} align="left">Account Status</th> : null}
                  {canManage || isPlatformAdmin ? <th style={tableHeaderCellStyle} align="left">Actions</th> : null}
                </tr>
              </thead>
              <tbody>
                {paginatedUsers.map((user) => {
                  const isProcessing = processingUserId === user.user_id;
                  const isCurrentUser = user.user_id === currentUser?.id;
                  const canEditRole = canEditRoleForUser(user) && !isCurrentUser;

                  return (
                    <tr key={user.user_id} style={{ ...tableRowStyle, opacity: isProcessing ? 0.6 : 1 }}>
                      <td style={tableCellStyle}>
                        <div style={{ display: "grid", gap: 6 }}>
                          <span style={userEmailStyle}>{user.email}</span>
                          {isCurrentUser ? <span style={getStatusBadgeStyle("neutral")}>You</span> : null}
                        </div>
                      </td>
                      <td style={tableCellStyle}>
                        <span style={userNameStyle}>{user.name || "No display name"}</span>
                      </td>
                      <td style={tableCellStyle}>
                        {isPlatformView ? (
                          <div style={{ display: "grid", gap: "8px" }}>
                            {user.is_platform_admin ? (
                              <span style={getStatusBadgeStyle("accent")}>Super Admin</span>
                            ) : null}
                            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                              <span style={countBadgeStyle}>{tenantCount(user)} tenant{tenantCount(user) === 1 ? "" : "s"}</span>
                              {tenantCount(user) === 0 ? <span style={getStatusBadgeStyle("warm")}>Unassigned</span> : null}
                            </div>
                            <span style={membershipSummaryStyle}>{formatMembershipSummary(user)}</span>
                          </div>
                        ) : canEditRole ? (
                          <RoleSelector
                            value={user.role}
                            onChange={(nextRole) => handleRoleChange(user.user_id, nextRole)}
                            disabled={isProcessing}
                            options={getRoleOptionsForUser(user)}
                          />
                        ) : (
                          user.role
                        )}
                      </td>
                      <td style={tableCellStyle}>
                        {isPlatformView ? (
                          <span style={getStatusBadgeStyle(user.is_platform_admin ? "accent" : "neutral")}>
                            {user.is_platform_admin ? "Global access" : "Tenant-only access"}
                          </span>
                        ) : (
                          <span style={getStatusBadgeStyle(user.status === "active" ? "success" : "neutral")}>
                            {user.status}
                          </span>
                        )}
                      </td>
                      <td style={tableCellStyleMuted}>{formatLastLogin(user)}</td>
                      {isPlatformAdmin ? (
                        <td style={tableCellStyle}>
                          <span style={getStatusBadgeStyle(user.is_active ? "success" : "danger")}>
                            {user.is_active ? "Active" : "Suspended"}
                          </span>
                        </td>
                      ) : null}
                      {canManage || isPlatformAdmin ? (
                        <td style={tableCellStyle}>
                          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                          {canRemoveUsers && !isCurrentUser ? (
                            <button
                              onClick={() => confirmRemove(user)}
                              style={getActionButtonStyle("danger")}
                              aria-label={`Remove ${user.email}`}
                              disabled={isProcessing}
                            >
                              Remove
                            </button>
                          ) : null}
                          {isPlatformAdmin && !isCurrentUser ? (
                            user.is_platform_admin ? (
                              <button
                                onClick={() => confirmDemote(user)}
                                style={getActionButtonStyle("ghost")}
                                aria-label={`Remove super admin from ${user.email}`}
                                disabled={isProcessing}
                              >
                                {isProcessing ? "Processing..." : "Remove Super Admin"}
                              </button>
                            ) : (
                              <button
                                onClick={() => confirmPromote(user)}
                                style={getActionButtonStyle("primary")}
                                aria-label={`Grant super admin to ${user.email}`}
                                disabled={isProcessing}
                              >
                                {isProcessing ? "Processing..." : "Grant Super Admin"}
                              </button>
                            )
                          ) : null}
                          {isPlatformAdmin && canSuspendUsers && !isCurrentUser ? (
                            user.is_active ? (
                              <button
                                onClick={() => confirmSuspend(user)}
                                style={getActionButtonStyle("danger")}
                                aria-label={`Suspend ${user.email}`}
                                disabled={isProcessing}
                              >
                                {isProcessing ? "Processing..." : "Suspend"}
                              </button>
                            ) : (
                              <button
                                onClick={() => confirmUnsuspend(user)}
                                style={getActionButtonStyle("secondary")}
                                aria-label={`Unsuspend ${user.email}`}
                                disabled={isProcessing}
                              >
                                {isProcessing ? "Processing..." : "Unsuspend"}
                              </button>
                            )
                          ) : null}
                          </div>
                        </td>
                      ) : null}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )
      ) : null}

      <div
        style={{
          marginTop: 18,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 8,
          flexWrap: "wrap",
          paddingTop: 14,
          borderTop: "1px solid rgba(15, 23, 42, 0.08)"
        }}
        aria-live="polite"
      >
        <div style={{ color: "#475467", fontSize: 14, fontWeight: 500 }}>
          {visibleUsers.length === 0
            ? "No matching users"
            : `Showing ${startIndex + 1}-${Math.min(startIndex + pageSize, visibleUsers.length)} of ${visibleUsers.length}`}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
            disabled={clampedPage <= 1}
            aria-label="Previous page"
            style={getActionButtonStyle("secondary")}
          >
            Previous
          </button>
          <span style={{ alignSelf: "center", minWidth: 90, textAlign: "center", color: "#344054", fontWeight: 600 }}>
            Page {clampedPage} / {totalPages}
          </span>
          <button
            onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
            disabled={clampedPage >= totalPages}
            aria-label="Next page"
            style={getActionButtonStyle("secondary")}
          >
            Next
          </button>
        </div>
      </div>

      <ConfirmDialog
        isOpen={confirmDialog.isOpen}
        title={confirmDialog.title}
        message={confirmDialog.message}
        confirmText={confirmDialog.action === "remove"
          ? "Remove"
          : confirmDialog.action === "suspend"
            ? "Suspend"
            : confirmDialog.action === "promote"
              ? "Grant"
              : confirmDialog.action === "demote"
                ? "Remove"
                : "Unsuspend"}
        cancelText="Cancel"
        variant={confirmDialog.action === "remove" || confirmDialog.action === "suspend" || confirmDialog.action === "demote" ? "danger" : "warning"}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />
    </div>
  );
}

function getPanelShellStyle(isPlatformView) {
  return {
    borderRadius: isPlatformView ? "26px" : "18px",
    padding: isPlatformView ? "24px" : "18px",
    border: "1px solid rgba(15, 23, 42, 0.08)",
    background: isPlatformView
      ? "linear-gradient(180deg, #fcfdff 0%, #f5f7fb 100%)"
      : "#ffffff",
    boxShadow: isPlatformView
      ? "0 24px 56px rgba(15, 23, 42, 0.10)"
      : "0 16px 36px rgba(15, 23, 42, 0.06)",
  };
}

function getQuickFilterButtonStyle(active, tone) {
  const tones = {
    neutral: {
      background: active ? "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)" : "#ffffff",
      color: active ? "#ffffff" : "#1f2937",
      border: active ? "1px solid transparent" : "1px solid rgba(15, 23, 42, 0.12)",
      shadow: active ? "0 16px 30px rgba(15, 23, 42, 0.18)" : "none",
    },
    accent: {
      background: active ? "linear-gradient(135deg, #0b6bcb 0%, #1d4ed8 100%)" : "#eef5ff",
      color: active ? "#ffffff" : "#164194",
      border: active ? "1px solid transparent" : "1px solid rgba(29, 78, 216, 0.12)",
      shadow: active ? "0 16px 30px rgba(29, 78, 216, 0.22)" : "none",
    },
    danger: {
      background: active ? "linear-gradient(135deg, #b42318 0%, #d92d20 100%)" : "#fff1f1",
      color: active ? "#ffffff" : "#b42318",
      border: active ? "1px solid transparent" : "1px solid rgba(185, 28, 28, 0.12)",
      shadow: active ? "0 16px 30px rgba(185, 28, 28, 0.20)" : "none",
    },
    warm: {
      background: active ? "linear-gradient(135deg, #9a3412 0%, #c2410c 100%)" : "#fff3ea",
      color: active ? "#ffffff" : "#9a3412",
      border: active ? "1px solid transparent" : "1px solid rgba(194, 65, 12, 0.14)",
      shadow: active ? "0 16px 30px rgba(194, 65, 12, 0.18)" : "none",
    },
  };

  const palette = tones[tone] || tones.neutral;
  return {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 10,
    minWidth: 150,
    padding: "12px 14px",
    borderRadius: 16,
    fontSize: 14,
    fontWeight: 700,
    cursor: "pointer",
    transition: "all 160ms ease",
    ...palette,
    boxShadow: palette.shadow,
  };
}

function getActionButtonStyle(variant) {
  const variants = {
    primary: {
      background: "linear-gradient(135deg, #0f766e 0%, #0f9f85 100%)",
      color: "#ffffff",
      border: "1px solid transparent",
      boxShadow: "0 14px 28px rgba(15, 118, 110, 0.18)",
    },
    secondary: {
      background: "#ffffff",
      color: "#1f2937",
      border: "1px solid rgba(15, 23, 42, 0.12)",
      boxShadow: "none",
    },
    danger: {
      background: "#fff1f1",
      color: "#b42318",
      border: "1px solid rgba(180, 35, 24, 0.14)",
      boxShadow: "none",
    },
    ghost: {
      background: "#f5f7fb",
      color: "#344054",
      border: "1px solid rgba(15, 23, 42, 0.08)",
      boxShadow: "none",
    },
    warning: {
      background: "#fbbf24",
      color: "#1f2937",
      border: "1px solid transparent",
      boxShadow: "0 10px 20px rgba(251, 191, 36, 0.24)",
    },
  };

  return {
    padding: "10px 14px",
    borderRadius: 12,
    fontSize: 13,
    fontWeight: 700,
    cursor: "pointer",
    transition: "all 160ms ease",
    ...variants[variant],
  };
}

function getStatusBadgeStyle(tone) {
  const tones = {
    accent: {
      background: "#e7efff",
      color: "#1d4ed8",
      border: "1px solid rgba(29, 78, 216, 0.16)",
    },
    neutral: {
      background: "#eef2f6",
      color: "#344054",
      border: "1px solid rgba(15, 23, 42, 0.08)",
    },
    success: {
      background: "#ecfdf3",
      color: "#027a48",
      border: "1px solid rgba(2, 122, 72, 0.14)",
    },
    danger: {
      background: "#fff1f1",
      color: "#b42318",
      border: "1px solid rgba(180, 35, 24, 0.14)",
    },
    warm: {
      background: "#fff6ed",
      color: "#c2410c",
      border: "1px solid rgba(194, 65, 12, 0.12)",
    },
  };

  return {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    width: "fit-content",
    padding: "5px 10px",
    borderRadius: 999,
    fontSize: 12,
    fontWeight: 700,
    letterSpacing: "0.01em",
    ...tones[tone],
  };
}

const headerShellStyle = {
  display: "flex",
  justifyContent: "space-between",
  gap: 16,
  alignItems: "flex-start",
  flexWrap: "wrap",
  marginBottom: 18,
};

const eyebrowStyle = {
  fontSize: 11,
  fontWeight: 800,
  textTransform: "uppercase",
  letterSpacing: "0.14em",
  color: "#0f766e",
  marginBottom: 8,
};

const headerTitleRowStyle = {
  display: "flex",
  gap: 12,
  alignItems: "center",
  flexWrap: "wrap",
  marginBottom: 8,
};

const headerTitleStyle = {
  margin: 0,
  fontSize: 28,
  lineHeight: 1.1,
  color: "#0f172a",
};

const headerCountBadgeStyle = {
  display: "inline-flex",
  alignItems: "center",
  padding: "7px 12px",
  borderRadius: 999,
  background: "#f0f9ff",
  border: "1px solid rgba(14, 116, 144, 0.12)",
  color: "#0f5f73",
  fontSize: 13,
  fontWeight: 700,
};

const headerSubtitleStyle = {
  margin: 0,
  maxWidth: 720,
  color: "#475467",
  fontSize: 15,
  lineHeight: 1.6,
};

const quickFilterStripStyle = {
  display: "flex",
  gap: 10,
  flexWrap: "wrap",
  marginBottom: 16,
};

const toolbarShellStyle = {
  display: "flex",
  gap: 10,
  flexWrap: "wrap",
  marginBottom: 18,
  padding: "14px",
  borderRadius: 18,
  border: "1px solid rgba(15, 23, 42, 0.08)",
  background: "rgba(255, 255, 255, 0.86)",
};

const controlStyle = {
  padding: "11px 14px",
  borderRadius: 12,
  border: "1px solid rgba(15, 23, 42, 0.12)",
  background: "#ffffff",
  color: "#0f172a",
  fontSize: 14,
  boxShadow: "inset 0 1px 2px rgba(15, 23, 42, 0.03)",
};

const emptyStateStyle = {
  padding: "40px",
  textAlign: "center",
  color: "#667085",
  borderRadius: 20,
  border: "1px dashed rgba(15, 23, 42, 0.16)",
  background: "rgba(255, 255, 255, 0.72)",
};

const tableShellStyle = {
  overflowX: "auto",
  borderRadius: 22,
  border: "1px solid rgba(15, 23, 42, 0.08)",
  background: "#ffffff",
  boxShadow: "0 16px 40px rgba(15, 23, 42, 0.08)",
};

const tableStyle = {
  width: "100%",
  borderCollapse: "separate",
  borderSpacing: 0,
};

const tableCaptionStyle = {
  textAlign: "left",
  padding: "16px 18px 8px 18px",
  color: "#667085",
  fontWeight: 600,
};

const tableHeaderCellStyle = {
  padding: "12px 18px",
  background: "#f8fafc",
  borderBottom: "1px solid rgba(15, 23, 42, 0.08)",
  color: "#475467",
  fontSize: 12,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  whiteSpace: "nowrap",
};

const sortButtonStyle = {
  background: "transparent",
  border: "none",
  padding: 0,
  font: "inherit",
  color: "inherit",
  fontWeight: 800,
  cursor: "pointer",
};

const tableRowStyle = {
  background: "#ffffff",
};

const tableCellStyle = {
  padding: "16px 18px",
  borderBottom: "1px solid rgba(15, 23, 42, 0.06)",
  verticalAlign: "top",
};

const tableCellStyleMuted = {
  ...tableCellStyle,
  color: "#475467",
  fontWeight: 500,
};

const userEmailStyle = {
  fontSize: 14,
  fontWeight: 700,
  color: "#101828",
};

const userNameStyle = {
  color: "#344054",
  fontWeight: 600,
};

const membershipSummaryStyle = {
  color: "#475467",
  lineHeight: 1.5,
  maxWidth: 340,
};

const mobileUserEmailStyle = {
  fontSize: 15,
  fontWeight: 700,
  color: "#101828",
  marginBottom: 4,
};

const mobileUserNameStyle = {
  color: "#475467",
  fontSize: 14,
};

const mobileMetaRowStyle = {
  display: "flex",
  justifyContent: "space-between",
  gap: 12,
  alignItems: "center",
  padding: "9px 0",
  borderTop: "1px solid rgba(15, 23, 42, 0.06)",
  color: "#344054",
  fontSize: 14,
};

const countBadgeStyle = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  minWidth: "28px",
  borderRadius: "999px",
  padding: "5px 10px",
  backgroundColor: "#eef5ff",
  color: "#1d4ed8",
  fontSize: "12px",
  fontWeight: 700,
  border: "1px solid rgba(29, 78, 216, 0.12)",
};