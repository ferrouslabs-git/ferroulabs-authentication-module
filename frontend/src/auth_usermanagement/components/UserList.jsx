import { useEffect, useMemo, useState } from "react";
import {
  getTenantUsers,
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

export function UserList({ className, canManage: canManageProp }) {
  const { token, tenantId, user: currentUser } = useAuth();
  const { canManage: canManageRole } = useRole();
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
  
  // Permission checks using standardized constants
  // Backwards compatible with canManage prop
  const canManage = canManageProp !== undefined 
    ? canManageProp 
    : checkPermission(currentUser, PERMISSIONS.REMOVE_USERS);
  
  const canSuspendUsers = checkPermission(currentUser, PERMISSIONS.SUSPEND_USERS);

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const loadUsers = async () => {
    if (!token || !tenantId) {
      setUsers([]);
      return;
    }

    setIsLoading(true);
    try {
      const res = await getTenantUsers(token, tenantId);
      setUsers(res);
    } catch (err) {
      toast.error(getErrorMessage('load_users', err));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, [token, tenantId]);

  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, roleFilter, statusFilter, pageSize]);

  const visibleUsers = useMemo(() => {
    const filtered = users.filter((u) => {
      const normalizedSearch = searchTerm.trim().toLowerCase();
      const matchesSearch =
        normalizedSearch.length === 0 ||
        u.email?.toLowerCase().includes(normalizedSearch) ||
        (u.name || "").toLowerCase().includes(normalizedSearch);

      const matchesRole = roleFilter === "all" || u.role === roleFilter;

      const accountStatus = u.is_active === false ? "suspended" : "active";
      const matchesStatus = statusFilter === "all" || accountStatus === statusFilter;

      return matchesSearch && matchesRole && matchesStatus;
    });

    const sorted = [...filtered].sort((a, b) => {
      const aValue = (a[sortConfig.key] ?? "").toString().toLowerCase();
      const bValue = (b[sortConfig.key] ?? "").toString().toLowerCase();

      if (aValue < bValue) return sortConfig.direction === "asc" ? -1 : 1;
      if (aValue > bValue) return sortConfig.direction === "asc" ? 1 : -1;
      return 0;
    });

    return sorted;
  }, [users, searchTerm, roleFilter, statusFilter, sortConfig]);

  const totalPages = Math.max(1, Math.ceil(visibleUsers.length / pageSize));
  const clampedPage = Math.min(currentPage, totalPages);
  const startIndex = (clampedPage - 1) * pageSize;
  const paginatedUsers = visibleUsers.slice(startIndex, startIndex + pageSize);

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

  const handleRoleChange = async (userId, role) => {
    const user = users.find(u => u.user_id === userId);
    setProcessingUserId(userId);
    
    try {
      await updateTenantUserRole(token, tenantId, userId, role);
      toast.success(`Updated ${user?.email}'s role to ${role}`);
      await loadUsers();
    } catch (err) {
      toast.error(getErrorMessage('update_role', err, { email: user.email }));
    } finally {
      setProcessingUserId(null);
    }
  };

  const confirmRemove = (user) => {
    setConfirmDialog({
      isOpen: true,
      action: 'remove',
      user,
      title: 'Remove User',
      message: `Are you sure you want to remove ${user.email} from this tenant? They will lose access immediately.`,
    });
  };

  const confirmSuspend = (user) => {
    setConfirmDialog({
      isOpen: true,
      action: 'suspend',
      user,
      title: 'Suspend User',
      message: `Are you sure you want to suspend ${user.email}? They will be unable to log in until unsuspended.`,
    });
  };

  const confirmUnsuspend = (user) => {
    setConfirmDialog({
      isOpen: true,
      action: 'unsuspend',
      user,
      title: 'Unsuspend User',
      message: `Are you sure you want to unsuspend ${user.email}? They will regain access immediately.`,
    });
  };

  const executeAction = async (action, user) => {
    if (!user) return;

    setProcessingUserId(user.user_id);
    setLastFailedOperation(null); // Clear previous failed operation
    
    try {
      if (action === 'remove') {
        await removeTenantUser(token, tenantId, user.user_id);
        toast.success(getSuccessMessage('remove_user', { email: user.email }));
      } else if (action === 'suspend') {
        await suspendUser(token, user.user_id);
        toast.success(getSuccessMessage('suspend_user', { email: user.email }));
      } else if (action === 'unsuspend') {
        await unsuspendUser(token, user.user_id);
        toast.success(getSuccessMessage('unsuspend_user', { email: user.email }));
      }
      await loadUsers();
    } catch (err) {
      const errorMsg = getErrorMessage(`${action}_user`, err, { email: user.email });
      toast.error(errorMsg);
      // Save failed operation for retry
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
    if (lastFailedOperation) {
      const { action, user } = lastFailedOperation;
      setLastFailedOperation(null);
      await executeAction(action, user);
    }
  };

  const handleCancel = () => {
    setConfirmDialog({ isOpen: false, action: null, user: null });
  };

  return (
    <div className={className}>
      {lastFailedOperation && (
        <div style={{
          backgroundColor: '#fff3cd',
          border: '1px solid #ffc107',
          borderRadius: '4px',
          padding: '12px 16px',
          marginBottom: '16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '12px'
        }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, color: '#856404', marginBottom: '4px' }}>
              Operation Failed
            </div>
            <div style={{ fontSize: '14px', color: '#856404' }}>
              {lastFailedOperation.errorMsg}
              {' '}
              ({lastFailedOperation.action} {lastFailedOperation.user.email})
            </div>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={handleRetry}
              style={{
                padding: '6px 12px',
                backgroundColor: '#ffc107',
                color: '#000',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '14px'
              }}
            >
              Retry
            </button>
            <button
              onClick={() => setLastFailedOperation(null)}
              style={{
                padding: '6px 12px',
                backgroundColor: 'transparent',
                color: '#856404',
                border: '1px solid #856404',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '14px'
              }}
            >
              Dismiss
            </button>
          </div>
        </div>
      )}
      
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
        <h3 style={{ margin: 0 }}>Tenant Users</h3>
        <button onClick={loadUsers} disabled={isLoading} aria-label="Refresh user list">
          {isLoading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Search by email or name"
          aria-label="Search users by email or name"
          style={{ padding: "8px 10px", minWidth: 220, flex: "1 1 220px" }}
        />
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          aria-label="Filter users by role"
          style={{ padding: "8px 10px" }}
        >
          <option value="all">All Roles</option>
          <option value="admin">Admin</option>
          <option value="member">Member</option>
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          aria-label="Filter users by account status"
          style={{ padding: "8px 10px" }}
        >
          <option value="all">All Statuses</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
        </select>
        <select
          value={String(pageSize)}
          onChange={(e) => setPageSize(Number(e.target.value))}
          aria-label="Users per page"
          style={{ padding: "8px 10px" }}
        >
          <option value="10">10 / page</option>
          <option value="25">25 / page</option>
          <option value="50">50 / page</option>
        </select>
      </div>

      {isLoading && users.length === 0 ? (
        <div style={{ padding: '40px', textAlign: 'center', color: '#666' }}>
          <div style={{ fontSize: '14px' }}>Loading users...</div>
        </div>
      ) : null}

      {!isLoading && users.length === 0 ? (
        <div style={{ padding: '40px', textAlign: 'center', color: '#666' }}>
          <div style={{ fontSize: '14px' }}>No users found in this tenant.</div>
        </div>
      ) : null}

      {paginatedUsers.length > 0 ? (
        isMobile ? (
          <div role="list" aria-label="Tenant users" style={{ display: "grid", gap: 10 }}>
            {paginatedUsers.map((u) => {
              const isProcessing = processingUserId === u.user_id;
              const isCurrentUser = u.user_id === currentUser?.user_id;

              return (
                <article
                  key={u.user_id}
                  role="listitem"
                  aria-label={`User ${u.email}`}
                  style={{
                    border: "1px solid #ddd",
                    borderRadius: 8,
                    padding: 12,
                    opacity: isProcessing ? 0.6 : 1,
                    background: "#fff"
                  }}
                >
                  <div><strong>Email:</strong> {u.email}</div>
                  <div><strong>Name:</strong> {u.name || "-"}</div>
                  <div>
                    <strong>Role:</strong>{" "}
                    {canManage && !isCurrentUser ? (
                      <RoleSelector
                        value={u.role}
                        onChange={(nextRole) => handleRoleChange(u.user_id, nextRole)}
                        disabled={isProcessing}
                      />
                    ) : (
                      u.role
                    )}
                  </div>
                  <div><strong>Status:</strong> {u.status}</div>
                  <div><strong>Last Login:</strong> {formatLastLogin(u)}</div>
                  {isPlatformAdmin ? (
                    <div>
                      <strong>Account:</strong>{" "}
                      <span style={{ color: u.is_active ? "#2e7d32" : "#b00020" }}>
                        {u.is_active ? "Active" : "Suspended"}
                      </span>
                    </div>
                  ) : null}
                  {canManage || isPlatformAdmin ? (
                    <div style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap" }}>
                      {canManage && !isCurrentUser && (
                        <button 
                          onClick={() => confirmRemove(u)} 
                          aria-label={`Remove ${u.email}`}
                          disabled={isProcessing}
                        >
                          Remove
                        </button>
                      )}
                      {isPlatformAdmin && !isCurrentUser && (
                        u.is_active ? (
                          <button
                            onClick={() => confirmSuspend(u)}
                            aria-label={`Suspend ${u.email}`}
                            disabled={isProcessing}
                          >
                            {isProcessing ? "Processing..." : "Suspend"}
                          </button>
                        ) : (
                          <button
                            onClick={() => confirmUnsuspend(u)}
                            aria-label={`Unsuspend ${u.email}`}
                            disabled={isProcessing}
                          >
                            {isProcessing ? "Processing..." : "Unsuspend"}
                          </button>
                        )
                      )}
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <caption style={{ textAlign: "left", padding: "0 0 8px 0", color: "#444" }}>
                Showing {paginatedUsers.length} of {visibleUsers.length} filtered users
              </caption>
              <thead>
                <tr>
                  <th align="left" aria-sort={getAriaSort("email")}>
                    <button onClick={() => setSort("email")} aria-label="Sort by email">
                      Email {sortConfig.key === "email" ? (sortConfig.direction === "asc" ? "▲" : "▼") : ""}
                    </button>
                  </th>
                  <th align="left" aria-sort={getAriaSort("name")}>
                    <button onClick={() => setSort("name")} aria-label="Sort by name">
                      Name {sortConfig.key === "name" ? (sortConfig.direction === "asc" ? "▲" : "▼") : ""}
                    </button>
                  </th>
                  <th align="left" aria-sort={getAriaSort("role")}>
                    <button onClick={() => setSort("role")} aria-label="Sort by role">
                      Role {sortConfig.key === "role" ? (sortConfig.direction === "asc" ? "▲" : "▼") : ""}
                    </button>
                  </th>
                  <th align="left">Status</th>
                  <th align="left">Last Login</th>
                  {isPlatformAdmin ? <th align="left">Account Status</th> : null}
                  {canManage || isPlatformAdmin ? <th align="left">Actions</th> : null}
                </tr>
              </thead>
              <tbody>
                {paginatedUsers.map((u) => {
                  const isProcessing = processingUserId === u.user_id;
                  const isCurrentUser = u.user_id === currentUser?.user_id;

                  return (
                    <tr key={u.user_id} style={{ opacity: isProcessing ? 0.6 : 1 }}>
                      <td>{u.email}</td>
                      <td>{u.name || "-"}</td>
                      <td>
                        {canManage && !isCurrentUser ? (
                          <RoleSelector
                            value={u.role}
                            onChange={(nextRole) => handleRoleChange(u.user_id, nextRole)}
                            disabled={isProcessing}
                          />
                        ) : (
                          u.role
                        )}
                      </td>
                      <td>{u.status}</td>
                      <td>{formatLastLogin(u)}</td>
                      {isPlatformAdmin ? (
                        <td>
                          <span style={{ color: u.is_active ? "#2e7d32" : "#b00020" }}>
                            {u.is_active ? "Active" : "Suspended"}
                          </span>
                        </td>
                      ) : null}
                      {canManage || isPlatformAdmin ? (
                        <td>
                          {canManage && !isCurrentUser && (
                            <button
                              onClick={() => confirmRemove(u)}
                              style={{ marginRight: 4 }}
                              aria-label={`Remove ${u.email}`}
                              disabled={isProcessing}
                            >
                              Remove
                            </button>
                          )}
                          {isPlatformAdmin && canSuspendUsers && !isCurrentUser && (
                            u.is_active ? (
                              <button
                                onClick={() => confirmSuspend(u)}
                                aria-label={`Suspend ${u.email}`}
                                disabled={isProcessing}
                              >
                                {isProcessing ? "Processing..." : "Suspend"}
                              </button>
                            ) : (
                              <button
                                onClick={() => confirmUnsuspend(u)}
                                aria-label={`Unsuspend ${u.email}`}
                                disabled={isProcessing}
                              >
                                {isProcessing ? "Processing..." : "Unsuspend"}
                              </button>
                            )
                          )}
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
          marginTop: 12,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 8,
          flexWrap: "wrap"
        }}
        aria-live="polite"
      >
        <div style={{ color: "#555", fontSize: 14 }}>
          {visibleUsers.length === 0
            ? "No matching users"
            : `Showing ${startIndex + 1}-${Math.min(startIndex + pageSize, visibleUsers.length)} of ${visibleUsers.length}`}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            disabled={clampedPage <= 1}
            aria-label="Previous page"
          >
            Previous
          </button>
          <span style={{ alignSelf: "center", minWidth: 90, textAlign: "center" }}>
            Page {clampedPage} / {totalPages}
          </span>
          <button
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            disabled={clampedPage >= totalPages}
            aria-label="Next page"
          >
            Next
          </button>
        </div>
      </div>

      <ConfirmDialog
        isOpen={confirmDialog.isOpen}
        title={confirmDialog.title}
        message={confirmDialog.message}
        confirmText={confirmDialog.action === 'remove' ? 'Remove' : confirmDialog.action === 'suspend' ? 'Suspend' : 'Unsuspend'}
        cancelText="Cancel"
        variant={confirmDialog.action === 'remove' || confirmDialog.action === 'suspend' ? 'danger' : 'warning'}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />
    </div>
  );
}
