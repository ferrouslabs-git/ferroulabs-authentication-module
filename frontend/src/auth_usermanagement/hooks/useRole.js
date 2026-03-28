import { useMemo } from "react";
import { useAuth } from "./useAuth";
import { useTenant } from "./useTenant";

/**
 * v3.0 permission-based role hook.
 *
 * When `scopeContext` is available (populated by AuthProvider after fetching
 * role definitions), permission checks use the resolved permission set.
 * Falls back to legacy numeric role levels for backward compatibility.
 */

const ROLE_LEVELS = {
  owner: 4,
  account_owner: 4,
  admin: 3,
  account_admin: 3,
  member: 2,
  account_member: 2,
  viewer: 1,
};

export function useRole() {
  const { scopeContext } = useAuth();
  const { tenant } = useTenant();

  const role = tenant?.role || null;
  const level = ROLE_LEVELS[role] || 0;
  const permissions = scopeContext?.resolved_permissions || [];
  const hasV3Context = scopeContext != null;

  const can = useMemo(() => {
    if (hasV3Context) {
      // v3: permission string lookup
      return (permission) => permissions.includes(permission);
    }
    // Legacy fallback: numeric role comparison
    return (minRole) => {
      const required = ROLE_LEVELS[minRole] || 0;
      return level >= required;
    };
  }, [hasV3Context, permissions, level]);

  return {
    role,
    permissions,
    can,
    isOwner: hasV3Context
      ? permissions.includes("account:delete")
      : ["owner", "account_owner"].includes(role),
    isAdminOrOwner: hasV3Context
      ? permissions.includes("members:manage")
      : level >= ROLE_LEVELS.admin,
  };
}
