const DEFAULT_ROLES = ["viewer", "member", "admin", "owner"];

export function RoleSelector({ value, onChange, disabled = false, className, options = DEFAULT_ROLES }) {
  return (
    <select
      className={className}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
    >
      {options.map((role) => (
        <option key={role} value={role}>{role}</option>
      ))}
    </select>
  );
}
