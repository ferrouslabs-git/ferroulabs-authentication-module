import { useMemo } from "react";
import { useTenant } from "./useTenant";

const ROLE_LEVELS = {
  owner: 4,
  admin: 3,
  member: 2,
  viewer: 1,
};

export function useRole() {
  const { tenant } = useTenant();
  const role = tenant?.role || null;
  const level = ROLE_LEVELS[role] || 0;

  const can = useMemo(
    () => (minRole) => {
      const required = ROLE_LEVELS[minRole] || 0;
      return level >= required;
    },
    [level],
  );

  return {
    role,
    can,
    isOwner: role === "owner",
    isAdminOrOwner: level >= ROLE_LEVELS.admin,
  };
}
