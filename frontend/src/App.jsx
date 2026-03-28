import { useEffect, useState } from 'react'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { AcceptInvitation, AdminDashboard, AUTH_CONFIG, CustomLoginForm, CustomSignupForm, ForgotPasswordForm, ProtectedRoute, TenantSwitcher, ToastProvider, useAuth } from './auth_usermanagement'
import { openHostedLogin, openHostedSignup } from './auth_usermanagement/services/cognitoClient'
import { createTenant } from './auth_usermanagement/services/authApi'

const ADMIN_ROUTE = '/admin'
const isCustomUI = AUTH_CONFIG.authMode === 'custom_ui'

function Shell({ children }) {
  const { isAuthenticated, isLoading, logout, loginWithTokens, user, tenantId, tenants } = useAuth()
  const navigate = useNavigate()
  const [isSignInRedirecting, setIsSignInRedirecting] = useState(false)
  const [isSignUpRedirecting, setIsSignUpRedirecting] = useState(false)
  const [authView, setAuthView] = useState('none') // "none" | "login" | "signup" | "forgot"
  const currentTenant = tenants.find((tenant) => tenant.id === tenantId) || null
  const canAccessAdmin = Boolean(user?.is_platform_admin || ['owner', 'admin', 'account_owner', 'account_admin'].includes(currentTenant?.role))

  const handleSignIn = async () => {
    if (isCustomUI) {
      setAuthView('login')
      return
    }
    setIsSignInRedirecting(true)
    try {
      await openHostedLogin()
    } catch (_error) {
      setIsSignInRedirecting(false)
    }
  }

  const handleSignUp = async () => {
    if (isCustomUI) {
      setAuthView('signup')
      return
    }
    setIsSignUpRedirecting(true)
    try {
      await openHostedSignup()
    } catch (_error) {
      setIsSignUpRedirecting(false)
    }
  }

  const handleSignOut = async () => {
    setAuthView('none')
    await logout()
  }

  const handleHome = () => {
    setAuthView('none')
    navigate(isAuthenticated ? '/dashboard' : '/')
  }

  const handleAdmin = () => {
    navigate(ADMIN_ROUTE)
  }

  // Reset auth view when user becomes authenticated
  useEffect(() => {
    if (isAuthenticated) setAuthView('none')
  }, [isAuthenticated])

  return (
    <div style={styles.appFrame}>
      <aside style={styles.sidebar}>
        <div>
          <h1 style={styles.logo}>FerrousLabs</h1>
          <p style={styles.sidebarText}>Authentication Demo</p>
        </div>

        <div style={styles.sidebarActions}>
          <button
            type="button"
            style={styles.homeButton}
            onClick={handleHome}
            disabled={isLoading}
          >
            Home
          </button>

          {isAuthenticated && canAccessAdmin ? (
            <button
              type="button"
              style={styles.adminButton}
              onClick={handleAdmin}
              disabled={isLoading}
            >
              User Management
            </button>
          ) : null}

          {!isAuthenticated ? (
            <>
              <button
                type="button"
                style={styles.signInButton}
                onClick={handleSignIn}
                disabled={isLoading || isSignInRedirecting || isSignUpRedirecting}
              >
                {isSignInRedirecting ? 'Redirecting...' : 'Sign In'}
              </button>
              <button
                type="button"
                style={styles.signUpButton}
                onClick={handleSignUp}
                disabled={isLoading || isSignInRedirecting || isSignUpRedirecting}
              >
                {isSignUpRedirecting ? 'Redirecting...' : 'Sign Up'}
              </button>
            </>
          ) : (
            <button
              type="button"
              style={styles.signOutButton}
              onClick={handleSignOut}
              disabled={isLoading}
            >
              Sign Out
            </button>
          )}
        </div>
      </aside>

      <main style={styles.mainContent}>
        {isCustomUI && authView === 'login' && !isAuthenticated ? (
          <div style={{ padding: 40, display: 'flex', justifyContent: 'center' }}>
            <CustomLoginForm
              onSuccess={async (tokens) => {
                await loginWithTokens(tokens)
              }}
              onNewPasswordRequired={() => {
                navigate('/')
              }}
              onSwitchToSignup={() => setAuthView('signup')}
              onForgotPassword={() => setAuthView('forgot')}
            />
          </div>
        ) : isCustomUI && authView === 'signup' && !isAuthenticated ? (
          <div style={{ padding: 40, display: 'flex', justifyContent: 'center' }}>
            <CustomSignupForm
              onConfirmed={() => setAuthView('login')}
              onSwitchToLogin={() => setAuthView('login')}
            />
          </div>
        ) : isCustomUI && authView === 'forgot' && !isAuthenticated ? (
          <div style={{ padding: 40, display: 'flex', justifyContent: 'center' }}>
            <ForgotPasswordForm
              onBackToLogin={() => setAuthView('login')}
            />
          </div>
        ) : (
          children
        )}
      </main>
    </div>
  )
}

function LandingPage() {
  return (
    <div style={styles.heroCard}>
      <p style={styles.kicker}>Welcome</p>
      <h2 style={styles.heroTitle}>Welcome to FerrousLab Authentication and User Management System</h2>
      <p style={styles.heroBody}>
        Secure sign-in, tenant-aware permissions, and invitation workflows in one reusable module.
      </p>
    </div>
  )
}

function DashboardPage() {
  const { user, tenantId, tenants, token } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const userName = user?.email ? user.email.split('@')[0] : 'user'
  const pendingAdminRoute = Boolean(location.state?.pendingAdminRoute)
  const showTenantSelectAssist = Boolean(
    location.state?.focusTenantSelector &&
    user?.is_platform_admin &&
    !tenantId &&
    tenants.length > 0,
  )

  const [tenantName, setTenantName] = useState('')
  const [isCreating, setIsCreating] = useState(false)
  const [createError, setCreateError] = useState('')

  useEffect(() => {
    if (!pendingAdminRoute || !tenantId) {
      return
    }
    navigate(ADMIN_ROUTE, { replace: true })
  }, [pendingAdminRoute, tenantId, navigate])

  const handleOpenUserManagement = () => {
    if (!tenantId && !user?.is_platform_admin) {
      return
    }
    navigate(ADMIN_ROUTE)
  }

  const handleCreateTenant = async (e) => {
    e.preventDefault()
    if (!tenantName.trim()) {
      setCreateError('Tenant name is required')
      return
    }
    if (!token) {
      setCreateError('Not authenticated')
      return
    }

    setIsCreating(true)
    setCreateError('')
    try {
      await createTenant(token, tenantName.trim(), 'free')
      setTenantName('')
      // Reload the page to fetch updated tenant list
      window.location.reload()
    } catch (error) {
      const errorDetail = error?.response?.data?.detail || error?.message || 'Failed to create tenant'
      setCreateError(errorDetail)
      setIsCreating(false)
    }
  }

  return (
    <div style={styles.heroCard}>
      <p style={styles.kicker}>Dashboard</p>
      <h2 style={styles.heroTitle}>Hi {userName}</h2>
      <p style={styles.heroBody}>You are signed in and viewing the authenticated page.</p>

      {showTenantSelectAssist ? (
        <div style={styles.assistBox}>
          <p style={styles.assistTitle}>Select a tenant for tenant-scoped management.</p>
          <p style={styles.assistBody}>
            You can already open the global user directory as a super admin. Select a tenant below when you want invite and tenant-role controls.
          </p>
        </div>
      ) : null}

      {tenants.length === 0 ? (
        <div style={styles.createTenantSection}>
          <p style={styles.sectionTitle}>No Tenants Yet</p>
          <p style={styles.sectionBody}>Create your first tenant to get started with User Management.</p>
          
          <form onSubmit={handleCreateTenant} style={styles.tenantForm}>
            <input
              type="text"
              placeholder="Enter tenant name (e.g., My Company)"
              value={tenantName}
              onChange={(e) => setTenantName(e.target.value)}
              disabled={isCreating}
              style={styles.tenantInput}
            />
            <button
              type="submit"
              disabled={isCreating}
              style={{
                ...styles.createTenantButton,
                ...(isCreating ? styles.createTenantButtonDisabled : {}),
              }}
            >
              {isCreating ? 'Creating...' : 'Create Tenant'}
            </button>
          </form>

          {createError && (
            <div style={styles.errorBox}>
              <p style={styles.errorText}>{createError}</p>
            </div>
          )}
        </div>
      ) : (
        <div style={styles.dashboardTools}>
          <TenantSwitcher label="Tenant For Admin Actions" />
          <button
            type="button"
            onClick={handleOpenUserManagement}
            disabled={!tenantId && !user?.is_platform_admin}
            style={{
              ...styles.dashboardAdminButton,
              ...(tenantId || user?.is_platform_admin ? null : styles.dashboardAdminButtonDisabled),
            }}
          >
            Open User Management
          </button>
        </div>
      )}
    </div>
  )
}

function CallbackPage() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }

  return (
    <div style={styles.heroCard}>
      <p style={styles.kicker}>Signing In</p>
      <h2 style={styles.heroTitle}>Completing Sign In...</h2>
      <p style={styles.heroBody}>{isLoading ? 'Please wait while we finalize your session.' : 'Redirecting...'}</p>
    </div>
  )
}

function App() {
  const { isAuthenticated } = useAuth()
  const inviteRoutePath = `${AUTH_CONFIG.invitePathPrefix}:token`

  return (
    <Routes>
      <Route
        path="/"
        element={<Shell>{isAuthenticated ? <Navigate to="/dashboard" replace /> : <LandingPage />}</Shell>}
      />
      <Route
        path="/dashboard"
        element={<Shell>{isAuthenticated ? <DashboardPage /> : <Navigate to="/" replace />}</Shell>}
      />
      <Route
        path={ADMIN_ROUTE}
        element={
          <Shell>
            <ProtectedRoute fallback={<Navigate to="/" replace />}>
              <ToastProvider>
                <AdminDashboard />
              </ToastProvider>
            </ProtectedRoute>
          </Shell>
        }
      />
      <Route path={AUTH_CONFIG.callbackPath} element={<Shell><CallbackPage /></Shell>} />
      <Route path={inviteRoutePath} element={<Shell><AcceptInvitation /></Shell>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

const styles = {
  appFrame: {
    minHeight: '100vh',
    display: 'flex',
    background: 'radial-gradient(circle at 20% 20%, #f8d9b6 0%, #f4efe4 30%, #d8e6ef 100%)',
    fontFamily: '"Trebuchet MS", "Segoe UI", sans-serif',
  },
  sidebar: {
    width: '280px',
    background: 'linear-gradient(180deg, #0f3443 0%, #1f5f73 100%)',
    color: '#f7fbff',
    padding: '28px 20px',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between',
  },
  logo: {
    margin: 0,
    fontSize: '1.6rem',
    letterSpacing: '0.04em',
  },
  sidebarText: {
    marginTop: '8px',
    opacity: 0.85,
  },
  sidebarActions: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  homeButton: {
    width: '100%',
    padding: '12px 14px',
    borderRadius: '10px',
    border: '1px solid rgba(255, 255, 255, 0.25)',
    background: 'rgba(255, 255, 255, 0.08)',
    color: '#f7fbff',
    fontWeight: 600,
    cursor: 'pointer',
  },
  adminButton: {
    width: '100%',
    padding: '12px 14px',
    borderRadius: '10px',
    border: '1px solid rgba(255, 209, 102, 0.45)',
    background: 'rgba(255, 209, 102, 0.18)',
    color: '#fff7df',
    fontWeight: 700,
    cursor: 'pointer',
  },
  signInButton: {
    width: '100%',
    padding: '12px 14px',
    borderRadius: '10px',
    border: 'none',
    background: '#ffd166',
    color: '#182026',
    fontWeight: 700,
    cursor: 'pointer',
  },
  signUpButton: {
    width: '100%',
    padding: '12px 14px',
    borderRadius: '10px',
    border: '1px solid rgba(255, 209, 102, 0.85)',
    background: 'rgba(255, 209, 102, 0.12)',
    color: '#fff3d0',
    fontWeight: 700,
    cursor: 'pointer',
  },
  signOutButton: {
    width: '100%',
    padding: '12px 14px',
    borderRadius: '10px',
    border: '1px solid rgba(255, 255, 255, 0.35)',
    background: 'rgba(255, 255, 255, 0.16)',
    color: '#f7fbff',
    fontWeight: 700,
    cursor: 'pointer',
  },
  mainContent: {
    flex: 1,
    padding: '28px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  heroCard: {
    width: 'min(860px, 100%)',
    background: 'rgba(255, 255, 255, 0.76)',
    border: '1px solid rgba(15, 52, 67, 0.12)',
    boxShadow: '0 22px 44px rgba(15, 52, 67, 0.18)',
    borderRadius: '20px',
    padding: '32px',
  },
  kicker: {
    margin: 0,
    color: '#1f5f73',
    fontWeight: 700,
    letterSpacing: '0.07em',
    textTransform: 'uppercase',
    fontSize: '0.78rem',
  },
  heroTitle: {
    marginTop: '10px',
    marginBottom: '14px',
    fontSize: '2.1rem',
    color: '#0f3443',
    lineHeight: 1.2,
  },
  heroBody: {
    margin: 0,
    color: '#2f4f5f',
    fontSize: '1rem',
    lineHeight: 1.6,
  },
  assistBox: {
    marginTop: '16px',
    marginBottom: '16px',
    padding: '12px 14px',
    borderRadius: '10px',
    background: '#f2f8ff',
    border: '1px solid #b9d4f2',
  },
  assistTitle: {
    margin: 0,
    color: '#163b5d',
    fontWeight: 700,
  },
  assistBody: {
    marginTop: '8px',
    marginBottom: 0,
    color: '#35556e',
    lineHeight: 1.5,
    fontSize: '0.95rem',
  },
  dashboardTools: {
    marginTop: '18px',
    display: 'flex',
    gap: '12px',
    alignItems: 'center',
    flexWrap: 'wrap',
  },
  dashboardAdminButton: {
    border: 'none',
    borderRadius: '8px',
    padding: '8px 12px',
    background: '#1f5f73',
    color: '#fff',
    fontWeight: 700,
    cursor: 'pointer',
  },
  dashboardAdminButtonDisabled: {
    background: '#9aa9b2',
    cursor: 'not-allowed',
  },
  createTenantSection: {
    marginTop: '24px',
    padding: '20px',
    borderRadius: '12px',
    background: '#f5faff',
    border: '1px solid #c8dff0',
  },
  sectionTitle: {
    margin: 0,
    marginBottom: '8px',
    color: '#0f3443',
    fontWeight: 700,
    fontSize: '1.1rem',
  },
  sectionBody: {
    margin: 0,
    marginBottom: '16px',
    color: '#2f4f5f',
    fontSize: '0.95rem',
    lineHeight: 1.5,
  },
  tenantForm: {
    display: 'flex',
    gap: '10px',
    marginBottom: '12px',
    flexWrap: 'wrap',
  },
  tenantInput: {
    flex: 1,
    minWidth: '200px',
    padding: '10px 12px',
    borderRadius: '8px',
    border: '1px solid #b9d4f2',
    fontSize: '0.95rem',
    fontFamily: 'inherit',
  },
  createTenantButton: {
    padding: '10px 16px',
    borderRadius: '8px',
    border: 'none',
    background: '#1f5f73',
    color: '#fff',
    fontWeight: 700,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  createTenantButtonDisabled: {
    background: '#9aa9b2',
    cursor: 'not-allowed',
  },
  errorBox: {
    marginTop: '12px',
    padding: '12px',
    borderRadius: '8px',
    background: '#ffe6e6',
    border: '1px solid #ff9999',
  },
  errorText: {
    margin: 0,
    color: '#c41616',
    fontSize: '0.9rem',
  },
}

export default App
