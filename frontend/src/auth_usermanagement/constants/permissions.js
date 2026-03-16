/**
 * Permission constants for auth_usermanagement module
 * 
 * These permissions align with backend role definitions and should be used
 * consistently across all components for permission checks.
 */

// User management permissions
export const PERMISSIONS = {
  // Tenant user management
  INVITE_USERS: 'invite_users',
  REMOVE_USERS: 'remove_users',
  SUSPEND_USERS: 'suspend_users',
  UPDATE_USER_ROLES: 'update_user_roles',
  VIEW_USERS: 'view_users',
  
  // Platform admin permissions
  MANAGE_TENANTS: 'manage_tenants',
  SUSPEND_ACCOUNTS: 'suspend_accounts',
  VIEW_ALL_USERS: 'view_all_users',
};

// Role definitions with their permissions
export const ROLE_PERMISSIONS = {
  owner: [
    PERMISSIONS.INVITE_USERS,
    PERMISSIONS.REMOVE_USERS,
    PERMISSIONS.SUSPEND_USERS,
    PERMISSIONS.UPDATE_USER_ROLES,
    PERMISSIONS.VIEW_USERS,
  ],
  admin: [
    PERMISSIONS.INVITE_USERS,
    PERMISSIONS.REMOVE_USERS,
    PERMISSIONS.SUSPEND_USERS,
    PERMISSIONS.UPDATE_USER_ROLES,
    PERMISSIONS.VIEW_USERS,
  ],
  member: [
    PERMISSIONS.VIEW_USERS,
  ],
  platform_admin: [
    ...Object.values(PERMISSIONS), // Platform admin has all permissions
  ],
};

// Helper function to check if a role has a specific permission
export function hasPermission(role, permission) {
  if (!role || !permission) return false;
  const permissions = ROLE_PERMISSIONS[role] || [];
  return permissions.includes(permission);
}

// Helper function to check if current user has a permission
export function checkPermission(currentUser, permission, tenantRole = null) {
  if (!currentUser) return false;
  
  // Platform admins have all permissions
  if (currentUser.is_platform_admin) return true;
  
  // Check role-based permissions
  return hasPermission(tenantRole || currentUser.role, permission);
}

// User-friendly permission labels
export const PERMISSION_LABELS = {
  [PERMISSIONS.INVITE_USERS]: 'Invite new users',
  [PERMISSIONS.REMOVE_USERS]: 'Remove users',
  [PERMISSIONS.SUSPEND_USERS]: 'Suspend users',
  [PERMISSIONS.UPDATE_USER_ROLES]: 'Update user roles',
  [PERMISSIONS.VIEW_USERS]: 'View users',
  [PERMISSIONS.MANAGE_TENANTS]: 'Manage tenants',
  [PERMISSIONS.SUSPEND_ACCOUNTS]: 'Suspend accounts',
  [PERMISSIONS.VIEW_ALL_USERS]: 'View all users',
};

export default PERMISSIONS;
