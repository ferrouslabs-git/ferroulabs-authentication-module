import React from 'react'
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom'
import { AuthProvider } from './auth_usermanagement/context/AuthProvider'
import { ToastProvider } from './auth_usermanagement/components/Toast'
import { useAuth } from './auth_usermanagement/hooks/useAuth'
import { LoginForm } from './auth_usermanagement/components/LoginForm'
import { TenantSwitcher } from './auth_usermanagement/components/TenantSwitcher'
import { UserList } from './auth_usermanagement/components/UserList'
import { InviteUserModal } from './auth_usermanagement/components/InviteUserModal'
import { AcceptInvitation } from './auth_usermanagement/components/AcceptInvitation'
import { useRole } from './auth_usermanagement/hooks/useRole'
import { AdminDashboard } from './auth_usermanagement/pages/AdminDashboard'
import { PERMISSIONS, checkPermission } from './auth_usermanagement/constants/permissions'

function Dashboard() {
  const { user, logout } = useAuth()
  const { canManage } = useRole()
  const location = useLocation()
  const [showInvite, setShowInvite] = React.useState(false)
  const canAccessAdmin = checkPermission(user, PERMISSIONS.REMOVE_USERS) || user?.is_platform_admin

  return (
    <div style={{ padding: '20px', fontFamily: 'system-ui' }}>
      <header style={{ marginBottom: '20px', borderBottom: '2px solid #333', paddingBottom: '10px' }}>
        <h1 style={{ margin: 0 }}>🔐 Auth Module Sandbox Test</h1>
        <p style={{ color: '#666', margin: '5px 0' }}>Testing portability of auth_usermanagement module</p>
        <nav style={{ marginTop: '12px', display: 'flex', gap: '16px', fontSize: '14px' }}>
          <Link 
            to="/" 
            style={{ 
              color: location.pathname === '/' ? '#0066cc' : '#666',
              textDecoration: 'none',
              fontWeight: location.pathname === '/' ? '600' : '400'
            }}
          >
            Home
          </Link>
          {canAccessAdmin && (
            <Link 
              to="/admin" 
              style={{ 
                color: location.pathname === '/admin' ? '#0066cc' : '#666',
                textDecoration: 'none',
                fontWeight: location.pathname === '/admin' ? '600' : '400'
              }}
            >
              Admin Dashboard
            </Link>
          )}
        </nav>
      </header>

      <div style={{ marginBottom: '20px', display: 'flex', gap: '20px', alignItems: 'center' }}>
        <div>
          <strong>User:</strong> {user?.email}
        </div>
        <TenantSwitcher />
        <button onClick={logout} style={{ marginLeft: 'auto', padding: '8px 16px' }}>
          Logout
        </button>
      </div>

      <div style={{ marginBottom: '20px' }}>
        {canManage && (
          <button 
            onClick={() => setShowInvite(true)}
            style={{ padding: '10px 20px', backgroundColor: '#0066cc', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
          >
            Invite Team Member
          </button>
        )}
      </div>

      <UserList canManage={canManage} />

      {showInvite && (
        <InviteUserModal
          onClose={() => setShowInvite(false)}
          onSuccess={() => {
            setShowInvite(false)
            window.location.reload()
          }}
        />
      )}
    </div>
  )
}

function App() {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <div>Loading...</div>
      </div>
    )
  }

  if (!user) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', backgroundColor: '#f5f5f5' }}>
        <div style={{ backgroundColor: 'white', padding: '40px', borderRadius: '8px', boxShadow: '0 2px 10px rgba(0,0,0,0.1)', maxWidth: '400px', width: '100%' }}>
          <h1 style={{ textAlign: 'center', marginBottom: '30px' }}>Auth Sandbox</h1>
          <LoginForm 
            onSuccess={() => {}}
            renderHeader={() => <p style={{ textAlign: 'center', color: '#666' }}>Sign in to test the auth module</p>}
          />
        </div>
      </div>
    )
  }

  // User is authenticated, render routes
  return (
    <Routes>
      <Route path="/admin" element={<AdminDashboard />} />
      <Route path="/" element={<Dashboard />} />
    </Routes>
  )
}

function AppWrapper() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            <Route path="/invite/:token" element={<AcceptInvitation />} />
            <Route path="/*" element={<App />} />
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default AppWrapper
