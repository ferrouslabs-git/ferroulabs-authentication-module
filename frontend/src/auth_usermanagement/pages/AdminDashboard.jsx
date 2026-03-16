import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { useRole } from "../hooks/useRole";
import { UserList } from "../components/UserList";
import { PlatformTenantPanel } from "../components/PlatformTenantPanel";
import { InviteUserModal } from "../components/InviteUserModal";
import { PERMISSIONS, checkPermission } from "../constants/permissions";

/**
 * AdminDashboard - Main admin interface for user management
 * 
 * Accessible to tenant admins and platform admins.
 * Combines user list management with invitation functionality.
 */
export function AdminDashboard() {
  const navigate = useNavigate();
  const { user, tenantId } = useAuth();
  const { role } = useRole();
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [viewMode, setViewMode] = useState(user?.is_platform_admin ? 'platform' : 'tenant');
  const hasTenantSelected = Boolean(tenantId);
  const isPlatformAdmin = user?.is_platform_admin;

  // Permission check
  const canManageUsers = checkPermission(user, PERMISSIONS.REMOVE_USERS, role);
  const canInviteUsers = viewMode === 'tenant' && hasTenantSelected && checkPermission(user, PERMISSIONS.INVITE_USERS, role);

  useEffect(() => {
    if (!isPlatformAdmin) {
      setViewMode('tenant');
      return;
    }

    if (!hasTenantSelected && viewMode === 'tenant') {
      setViewMode('platform');
    }
  }, [hasTenantSelected, isPlatformAdmin, viewMode]);

  // Refresh user list after invitation
  const handleInviteSuccess = () => {
    setRefreshKey(prev => prev + 1);
    setShowInviteModal(false);
  };

  if (!hasTenantSelected && !isPlatformAdmin) {
    return (
      <div style={{
        padding: '40px 20px',
        textAlign: 'center',
        maxWidth: '680px',
        margin: '0 auto'
      }}>
        <div style={{
          fontSize: '44px',
          marginBottom: '16px'
        }}>
          🧭
        </div>
        <h2 style={{ marginBottom: '12px', color: '#333' }}>
          No tenant selected
        </h2>
        <p style={{ color: '#666', lineHeight: 1.6, marginBottom: '20px' }}>
          You don't have any tenant memberships yet. Ask a tenant owner or admin to invite you before using user management.
        </p>
        <button
          type="button"
          onClick={() => navigate('/dashboard')}
          style={{
            backgroundColor: '#1976d2',
            color: '#fff',
            border: 'none',
            borderRadius: '8px',
            padding: '10px 18px',
            fontWeight: 600,
            cursor: 'pointer'
          }}
        >
          Go To Dashboard
        </button>
      </div>
    );
  }

  if (!canManageUsers && !isPlatformAdmin) {
    return (
      <div style={{
        padding: '40px 20px',
        textAlign: 'center',
        maxWidth: '600px',
        margin: '0 auto'
      }}>
        <div style={{
          fontSize: '48px',
          marginBottom: '16px'
        }}>
          🔒
        </div>
        <h2 style={{ marginBottom: '12px', color: '#333' }}>
          Access Denied
        </h2>
        <p style={{ color: '#666', lineHeight: 1.6 }}>
          You don't have permission to access the admin dashboard.
          <br />
          Only tenant admins and super admins can manage users.
        </p>
        <p style={{ marginTop: '24px', fontSize: '14px', color: '#999' }}>
          Your current role: <strong>{role}</strong>
        </p>
      </div>
    );
  }

  return (
    <div style={{
      maxWidth: '1200px',
      margin: '0 auto',
      padding: '20px'
    }}>
      {/* Header */}
      <div style={{
        marginBottom: '24px',
        borderBottom: '2px solid #e0e0e0',
        paddingBottom: '16px'
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px'
        }}>
          <div>
            <h1 style={{ margin: '0 0 8px 0', fontSize: '28px', color: '#333' }}>
              User Management
            </h1>
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '14px', color: '#666' }}>
                Role: <strong>{role || 'none'}</strong>
              </span>
              {isPlatformAdmin && (
                <span style={{
                  backgroundColor: '#9c27b0',
                  color: 'white',
                  padding: '4px 12px',
                  borderRadius: '12px',
                  fontSize: '12px',
                  fontWeight: 600
                }}>
                  Super Admin
                </span>
              )}
              {tenantId && (
                <span style={{ fontSize: '14px', color: '#666' }}>
                  Tenant: <code style={{
                    backgroundColor: '#f5f5f5',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    fontSize: '13px'
                  }}>{tenantId}</code>
                </span>
              )}
            </div>
          </div>

          {isPlatformAdmin ? (
            <div style={{ display: 'inline-flex', gap: '8px', flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={() => setViewMode('platform')}
                style={{
                  backgroundColor: viewMode === 'platform' ? '#0f766e' : '#e6f4f1',
                  color: viewMode === 'platform' ? '#fff' : '#0f766e',
                  border: '1px solid #0f766e',
                  borderRadius: '999px',
                  padding: '8px 14px',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                Global Directory
              </button>
              <button
                type="button"
                onClick={() => setViewMode('tenant')}
                disabled={!hasTenantSelected}
                style={{
                  backgroundColor: viewMode === 'tenant' ? '#1976d2' : '#eef4fb',
                  color: viewMode === 'tenant' ? '#fff' : '#1976d2',
                  border: '1px solid #1976d2',
                  borderRadius: '999px',
                  padding: '8px 14px',
                  fontWeight: 600,
                  cursor: hasTenantSelected ? 'pointer' : 'not-allowed',
                  opacity: hasTenantSelected ? 1 : 0.55
                }}
              >
                Tenant Management
              </button>
            </div>
          ) : null}

          {canInviteUsers && (
            <button
              onClick={() => setShowInviteModal(true)}
              style={{
                backgroundColor: '#1976d2',
                color: 'white',
                border: 'none',
                padding: '10px 20px',
                borderRadius: '6px',
                fontSize: '15px',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px'
              }}
              onMouseOver={(e) => e.target.style.backgroundColor = '#1565c0'}
              onMouseOut={(e) => e.target.style.backgroundColor = '#1976d2'}
            >
              <span style={{ fontSize: '18px' }}>+</span>
              Invite User
            </button>
          )}
        </div>
      </div>

      {isPlatformAdmin && viewMode === 'platform' ? (
        <div style={{
          marginBottom: '20px',
          padding: '14px 16px',
          borderRadius: '8px',
          backgroundColor: '#eef8f6',
          border: '1px solid #b7dfd7',
          color: '#14564d'
        }}>
          You are viewing all users across the platform. Select a tenant only when you want tenant-specific invites, role changes, or removals.
        </div>
      ) : null}

      <div style={{
        display: 'grid',
        gap: '20px',
        gridTemplateColumns: 'minmax(0, 1fr)',
        alignItems: 'start'
      }}>
        {isPlatformAdmin && viewMode === 'platform' ? <PlatformTenantPanel /> : null}

        <UserList
          key={refreshKey}
          canManage={canManageUsers}
          mode={viewMode}
          missingTenantMessage="Select a tenant to load users."
          style={{
            backgroundColor: 'white',
            borderRadius: '8px',
            padding: '20px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
          }}
        />
      </div>

      {/* Invite Modal */}
      {showInviteModal && (
        <InviteUserModal
          onClose={() => setShowInviteModal(false)}
          onSuccess={handleInviteSuccess}
        />
      )}
    </div>
  );
}
