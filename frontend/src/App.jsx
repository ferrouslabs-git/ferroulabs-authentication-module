import { useState } from 'react'
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { useAuth } from './auth_usermanagement'
import { openHostedLogin, openHostedSignup } from './auth_usermanagement/services/cognitoClient'

function Shell({ children }) {
  const { isAuthenticated, isLoading, logout } = useAuth()
  const navigate = useNavigate()
  const [isSignInRedirecting, setIsSignInRedirecting] = useState(false)
  const [isSignUpRedirecting, setIsSignUpRedirecting] = useState(false)

  const handleSignIn = async () => {
    setIsSignInRedirecting(true)
    try {
      await openHostedLogin()
    } catch (_error) {
      setIsSignInRedirecting(false)
    }
  }

  const handleSignUp = async () => {
    setIsSignUpRedirecting(true)
    try {
      await openHostedSignup()
    } catch (_error) {
      setIsSignUpRedirecting(false)
    }
  }

  const handleSignOut = async () => {
    await logout()
  }

  const handleHome = () => {
    navigate(isAuthenticated ? '/dashboard' : '/')
  }

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

      <main style={styles.mainContent}>{children}</main>
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
  const { user } = useAuth()
  const userName = user?.email ? user.email.split('@')[0] : 'user'

  return (
    <div style={styles.heroCard}>
      <p style={styles.kicker}>Dashboard</p>
      <h2 style={styles.heroTitle}>Hi {userName}</h2>
      <p style={styles.heroBody}>You are signed in and viewing the authenticated page.</p>
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
      <Route path="/callback" element={<Shell><CallbackPage /></Shell>} />
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
}

export default App
