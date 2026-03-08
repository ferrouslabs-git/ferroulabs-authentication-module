import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { getInvitationDetails, acceptInvitation } from '../services/authApi';
import { LoginForm } from './LoginForm';

export function AcceptInvitation() {
  const { token } = useParams();
  const { user, token: authToken } = useAuth();
  const navigate = useNavigate();
  
  const [invitation, setInvitation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [accepting, setAccepting] = useState(false);

  // Load invitation details
  useEffect(() => {
    async function loadInvitation() {
      try {
        setLoading(true);
        const data = await getInvitationDetails(token);
        setInvitation(data);
        setError(null);
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to load invitation');
      } finally {
        setLoading(false);
      }
    }
    
    if (token) {
      loadInvitation();
    }
  }, [token]);

  // Save invitation URL for post-login redirect
  useEffect(() => {
    if (!user && invitation) {
      localStorage.setItem('trustos_post_login_redirect', window.location.pathname);
    }
  }, [user, invitation]);

  async function handleAccept() {
    try {
      setAccepting(true);
      setError(null);
      await acceptInvitation(authToken, token);
      // Redirect to dashboard after successful acceptance
      navigate('/', { replace: true });
      window.location.reload(); // Reload to refresh tenant list
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to accept invitation');
      setAccepting(false);
    }
  }

  if (loading) {
    return (
      <div style={styles.container}>
        <div style={styles.card}>
          <div style={styles.loading}>Loading invitation...</div>
        </div>
      </div>
    );
  }

  if (error && !invitation) {
    return (
      <div style={styles.container}>
        <div style={styles.card}>
          <h2 style={styles.title}>❌ Invalid Invitation</h2>
          <p style={styles.error}>{error}</p>
          <button onClick={() => navigate('/')} style={styles.button}>
            Go to Dashboard
          </button>
        </div>
      </div>
    );
  }

  if (invitation?.is_expired) {
    return (
      <div style={styles.container}>
        <div style={styles.card}>
          <h2 style={styles.title}>⏰ Invitation Expired</h2>
          <p style={styles.message}>
            This invitation to <strong>{invitation.tenant_name}</strong> has expired.
          </p>
          <p style={styles.subtext}>
            Please contact the team administrator for a new invitation.
          </p>
          <button onClick={() => navigate('/')} style={styles.button}>
            Go to Dashboard
          </button>
        </div>
      </div>
    );
  }

  if (invitation?.is_accepted) {
    return (
      <div style={styles.container}>
        <div style={styles.card}>
          <h2 style={styles.title}>✅ Already Accepted</h2>
          <p style={styles.message}>
            You've already accepted this invitation to <strong>{invitation.tenant_name}</strong>.
          </p>
          <button onClick={() => navigate('/')} style={styles.button}>
            Go to Dashboard
          </button>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div style={styles.container}>
        <div style={styles.card}>
          <h2 style={styles.title}>📧 You've Been Invited!</h2>
          <div style={styles.inviteInfo}>
            <p style={styles.message}>
              You've been invited to join <strong>{invitation?.tenant_name}</strong> as a <strong>{invitation?.role}</strong>.
            </p>
            <p style={styles.subtext}>
              Email: {invitation?.email}
            </p>
          </div>
          <p style={styles.instruction}>Please sign in to accept this invitation:</p>
          <LoginForm 
            onSuccess={() => {
              // After login, the component will re-render with user set
            }}
          />
        </div>
      </div>
    );
  }

  // User is logged in, check if email matches
  const emailMatch = user.email?.toLowerCase() === invitation?.email?.toLowerCase();
  
  if (!emailMatch) {
    return (
      <div style={styles.container}>
        <div style={styles.card}>
          <h2 style={styles.title}>⚠️ Email Mismatch</h2>
          <p style={styles.message}>
            This invitation was sent to <strong>{invitation?.email}</strong>, but you're logged in as <strong>{user.email}</strong>.
          </p>
          <p style={styles.subtext}>
            Please sign in with the invited email address to accept this invitation.
          </p>
          <button onClick={() => navigate('/')} style={styles.button}>
            Go to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <h2 style={styles.title}>📧 Invitation</h2>
        <div style={styles.inviteInfo}>
          <p style={styles.message}>
            You've been invited to join <strong>{invitation?.tenant_name}</strong>
          </p>
          <div style={styles.details}>
            <div style={styles.detailRow}>
              <span style={styles.label}>Email:</span>
              <span>{invitation?.email}</span>
            </div>
            <div style={styles.detailRow}>
              <span style={styles.label}>Role:</span>
              <span style={styles.roleBadge}>{invitation?.role}</span>
            </div>
            {invitation?.expires_at && (
              <div style={styles.detailRow}>
                <span style={styles.label}>Expires:</span>
                <span>{new Date(invitation.expires_at).toLocaleDateString()}</span>
              </div>
            )}
          </div>
        </div>
        
        {error && (
          <div style={styles.errorBox}>{error}</div>
        )}
        
        <div style={styles.actions}>
          <button 
            onClick={handleAccept} 
            disabled={accepting}
            style={{...styles.button, ...styles.primaryButton}}
          >
            {accepting ? 'Accepting...' : 'Accept Invitation'}
          </button>
          <button 
            onClick={() => navigate('/')} 
            style={styles.secondaryButton}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

const styles = {
  container: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: '100vh',
    backgroundColor: '#f5f5f5',
    padding: '20px',
  },
  card: {
    backgroundColor: 'white',
    padding: '40px',
    borderRadius: '8px',
    boxShadow: '0 2px 10px rgba(0,0,0,0.1)',
    maxWidth: '500px',
    width: '100%',
  },
  title: {
    textAlign: 'center',
    marginBottom: '20px',
    fontSize: '24px',
  },
  inviteInfo: {
    backgroundColor: '#f8f9fa',
    padding: '20px',
    borderRadius: '6px',
    marginBottom: '20px',
  },
  message: {
    fontSize: '16px',
    marginBottom: '10px',
    lineHeight: '1.5',
  },
  subtext: {
    fontSize: '14px',
    color: '#666',
    marginBottom: '10px',
  },
  instruction: {
    fontSize: '14px',
    color: '#666',
    marginBottom: '15px',
    textAlign: 'center',
  },
  details: {
    marginTop: '15px',
  },
  detailRow: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '8px 0',
    borderBottom: '1px solid #e0e0e0',
  },
  label: {
    fontWeight: '600',
    color: '#555',
  },
  roleBadge: {
    padding: '2px 8px',
    backgroundColor: '#e3f2fd',
    color: '#1976d2',
    borderRadius: '4px',
    fontSize: '14px',
    fontWeight: '500',
  },
  actions: {
    display: 'flex',
    gap: '10px',
    marginTop: '20px',
  },
  button: {
    flex: 1,
    padding: '12px 24px',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '16px',
    fontWeight: '500',
  },
  primaryButton: {
    backgroundColor: '#0066cc',
    color: 'white',
  },
  secondaryButton: {
    flex: 1,
    padding: '12px 24px',
    backgroundColor: '#f5f5f5',
    color: '#333',
    border: '1px solid #ddd',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '16px',
  },
  error: {
    color: '#d32f2f',
    textAlign: 'center',
    marginTop: '10px',
  },
  errorBox: {
    backgroundColor: '#ffebee',
    color: '#c62828',
    padding: '12px',
    borderRadius: '4px',
    marginBottom: '15px',
    textAlign: 'center',
  },
  loading: {
    textAlign: 'center',
    padding: '40px',
    color: '#666',
  },
};
