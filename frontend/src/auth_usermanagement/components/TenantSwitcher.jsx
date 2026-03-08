import { useTenant } from "../hooks/useTenant";

export function TenantSwitcher({ className, label = "Current Tenant" }) {
  const { tenantId, tenants, changeTenant } = useTenant();

  if (!tenants.length) {
    return null;
  }

  return (
    <div className={className}>
      <label htmlFor="tenant-switcher">{label}: </label>
      <select
        id="tenant-switcher"
        value={tenantId || ""}
        onChange={(e) => changeTenant(e.target.value)}
      >
        {tenants.map((t) => (
          <option key={t.id} value={t.id}>
            {t.name} ({t.role})
          </option>
        ))}
      </select>
    </div>
  );
}
