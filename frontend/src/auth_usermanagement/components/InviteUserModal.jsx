import { useState, useEffect } from "react";
import { inviteTenantUser, getTenantUsers } from "../services/authApi";
import { useAuth } from "../hooks/useAuth";
import { useRole } from "../hooks/useRole";
import { useToast } from "./Toast";
import { PERMISSIONS, checkPermission } from "../constants/permissions";
import { getErrorMessage, getSuccessMessage } from "../utils/errorHandling";

export function InviteUserModal({ className, onClose, onSuccess }) {
  const { token, tenantId, user: currentUser } = useAuth();
  const { canManage } = useRole();
  const toast = useToast();
  
  // Permission check using standardized constant
  const canInvite = checkPermission(currentUser, PERMISSIONS.INVITE_USERS);
  
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [validationError, setValidationError] = useState("");
  const [existingUsers, setExistingUsers] = useState([]);

  // Load existing users to check for duplicates
  useEffect(() => {
    async function loadUsers() {
      if (token && tenantId) {
        try {
          const users = await getTenantUsers(token, tenantId);
          setExistingUsers(users);
        } catch (err) {
          // Silent fail - duplicate check is nice-to-have
        }
      }
    }
    loadUsers();
  }, [token, tenantId]);

  // Email validation
  const validateEmail = (email) => {
    const trimmed = email.trim().toLowerCase();
    if (!trimmed) {
      return "Email is required";
    }
    
    // Basic email format validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(trimmed)) {
      return "Please enter a valid email address";
    }
    
    // Check for duplicate users
    const isDuplicate = existingUsers.some(
      user => user.email.toLowerCase() === trimmed
    );
    if (isDuplicate) {
      return "This email is already a member of this tenant";
    }
    
    return null;
  };

  const handleEmailChange = (e) => {
    setEmail(e.target.value);
    setValidationError(""); // Clear validation error on change
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    
    // Permission check using standardized constant
    if (!canInvite) {
      toast.error("You don't have permission to invite users");
      return;
    }

    // Validate email
    const emailError = validateEmail(email);
    if (emailError) {
      setValidationError(emailError);
      return;
    }

    setIsSubmitting(true);
    setValidationError("");

    try {
      const result = await inviteTenantUser(token, tenantId, email.trim(), role);
      toast.success(getSuccessMessage('invite_user', { email }));
      
      if (onSuccess) {
        await onSuccess();
      }
      if (onClose) {
        onClose();
      }
    } catch (err) {
      const errorMsg = getErrorMessage('invite_user', err, { email });
      toast.error(errorMsg);
      setValidationError(errorMsg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
      onClick={onClose}
    >
      <form
        className={className}
        onSubmit={handleSubmit}
        onClick={(e) => e.stopPropagation()}
        style={{ 
          background: "#fff", 
          padding: 24, 
          minWidth: 400,
          borderRadius: 8,
          boxShadow: '0 4px 20px rgba(0, 0, 0, 0.15)',
        }}
      >
        <h3 style={{ marginTop: 0 }}>Invite User</h3>
        
        <label htmlFor="invite-email" style={{ display: 'block', marginBottom: 4, fontWeight: 500 }}>
          Email <span style={{ color: '#d32f2f' }}>*</span>
        </label>
        <input
          id="invite-email"
          type="email"
          value={email}
          onChange={handleEmailChange}
          style={{ 
            width: "100%", 
            marginBottom: validationError ? 4 : 16,
            padding: '8px 12px',
            border: validationError ? '2px solid #d32f2f' : '1px solid #ddd',
            borderRadius: 4,
            fontSize: 14,
          }}
          placeholder="user@company.com"
          disabled={isSubmitting}
          autoFocus
          required
        />
        {validationError && (
          <p style={{ color: "#d32f2f", fontSize: 12, margin: '0 0 16px 0' }}>
            {validationError}
          </p>
        )}

        <label htmlFor="invite-role" style={{ display: 'block', marginBottom: 4, fontWeight: 500 }}>
          Role <span style={{ color: '#d32f2f' }}>*</span>
        </label>
        <select
          id="invite-role"
          value={role}
          onChange={(e) => setRole(e.target.value)}
          style={{ 
            width: "100%", 
            marginBottom: 20,
            padding: '8px 12px',
            border: '1px solid #ddd',
            borderRadius: 4,
            fontSize: 14,
          }}
          disabled={isSubmitting}
        >
          <option value="viewer">Viewer</option>
          <option value="member">Member</option>
          <option value="admin">Admin</option>
        </select>

        <div style={{ display: "flex", gap: 12, justifyContent: 'flex-end' }}>
          <button 
            type="button" 
            onClick={onClose}
            style={{
              padding: '8px 16px',
              border: '1px solid #ddd',
              borderRadius: 4,
              background: '#f5f5f5',
              cursor: 'pointer',
            }}
            disabled={isSubmitting}
          >
            Cancel
          </button>
          <button 
            type="submit" 
            disabled={isSubmitting || !email.trim()}
            style={{
              padding: '8px 24px',
              border: 'none',
              borderRadius: 4,
              background: isSubmitting || !email.trim() ? '#ccc' : '#0066cc',
              color: 'white',
              cursor: isSubmitting || !email.trim() ? 'not-allowed' : 'pointer',
              fontWeight: 500,
            }}
          >
            {isSubmitting ? "Sending..." : "Send Invitation"}
          </button>
        </div>
      </form>
    </div>
  );
}
