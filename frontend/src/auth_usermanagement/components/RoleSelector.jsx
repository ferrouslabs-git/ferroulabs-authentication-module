export function RoleSelector({ value, onChange, disabled = false, className }) {
  return (
    <select
      className={className}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
    >
      <option value="viewer">viewer</option>
      <option value="member">member</option>
      <option value="admin">admin</option>
      <option value="owner">owner</option>
    </select>
  );
}
