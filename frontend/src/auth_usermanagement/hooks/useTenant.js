import { useMemo } from "react";
import { useAuth } from "./useAuth";

export function useTenant() {
  const { tenantId, tenants, changeTenant } = useAuth();

  const currentTenant = useMemo(
    () => tenants.find((t) => t.id === tenantId) || null,
    [tenants, tenantId],
  );

  return {
    tenantId,
    tenant: currentTenant,
    tenants,
    changeTenant,
  };
}
