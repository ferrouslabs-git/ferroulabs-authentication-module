import { useState } from "react";
import { useAuth } from "../hooks/useAuth";
import { useRole } from "../hooks/useRole";
import { UserList } from "../components/UserList";
import { InviteUserModal } from "../components/InviteUserModal";
import { PERMISSIONS, checkPermission } from "../constants/permissions";

/**
 * AdminDashboard - Main admin interface for user management
 * 
 * Accessible to tenant admins and platform admins.
 * Combines user list management with invitation functionality.
 */
export function AdminDashboard() {
  const { user, tenantId } = useAuth();
  const { role } = useRole();
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  // Permission check
  const canManageUsers = checkPermission(user, PERMISSIONS.REMOVE_USERS);
  const canInviteUsers = checkPermission(user, PERMISSIONS.INVITE_USERS);
  const isPlatformAdmin = user?.is_platform_admin;

  // Refresh user list after invitation
  const handleInviteSuccess = () => {
    setRefreshKey(prev => prev + 1);
    setShowInviteModal(false);
  };

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
          Only tenant admins and platform administrators can manage users.
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
                Role: <strong>{role}</strong>
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
                  Platform Admin
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

      {/* User List */}
      <UserList
        key={refreshKey}
        canManage={canManageUsers}
        style={{
          backgroundColor: 'white',
          borderRadius: '8px',
          padding: '20px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
        }}
      />

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
