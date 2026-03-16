// @vitest-environment jsdom

import React from 'react'
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { MemoryRouter } from 'react-router-dom'
import App from './App'

const authState = {
  isAuthenticated: false,
  isLoading: false,
  logout: vi.fn(),
  user: null,
  tenantId: null,
  tenants: [],
}

vi.mock('./auth_usermanagement/services/cognitoClient', () => ({
  openHostedLogin: vi.fn(async () => {}),
  openHostedSignup: vi.fn(async () => {}),
}))

vi.mock('./auth_usermanagement', () => ({
  AUTH_CONFIG: {
    callbackPath: '/callback',
    invitePathPrefix: '/invite/',
  },
  useAuth: () => authState,
  AcceptInvitation: () => <div>Mock Accept Invitation</div>,
  AdminDashboard: () => <div>Mock Admin Dashboard</div>,
  TenantSwitcher: ({ label = 'Current Tenant' }) => <div>{label}</div>,
  ToastProvider: ({ children }) => <>{children}</>,
  ProtectedRoute: ({ children, fallback = null }) => {
    if (!authState.isAuthenticated) {
      return fallback
    }
    return children
  },
}))

function renderApp(initialEntry = '/') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <App />
    </MemoryRouter>,
  )
}

describe('Admin Routing Visibility', () => {
  beforeEach(() => {
    authState.isAuthenticated = false
    authState.isLoading = false
    authState.logout = vi.fn()
    authState.user = null
    authState.tenantId = null
    authState.tenants = []
  })

  afterEach(() => {
    cleanup()
  })

  it('shows User Management nav button for authenticated tenant admin', () => {
    authState.isAuthenticated = true
    authState.user = { is_platform_admin: false }
    authState.tenantId = 'tenant-1'
    authState.tenants = [{ id: 'tenant-1', role: 'admin' }]

    renderApp('/dashboard')

    expect(screen.getByRole('button', { name: /^user management$/i })).toBeInTheDocument()
  })

  it('hides User Management nav button for authenticated tenant member', () => {
    authState.isAuthenticated = true
    authState.user = { is_platform_admin: false }
    authState.tenantId = 'tenant-1'
    authState.tenants = [{ id: 'tenant-1', role: 'member' }]

    renderApp('/dashboard')

    expect(screen.queryByRole('button', { name: /^user management$/i })).not.toBeInTheDocument()
  })

  it('shows User Management nav button for platform admin without selected tenant', () => {
    authState.isAuthenticated = true
    authState.user = { is_platform_admin: true }
    authState.tenantId = null
    authState.tenants = [{ id: 'tenant-1', role: 'viewer', name: 'Tenant One' }]

    renderApp('/dashboard')

    expect(screen.getByRole('button', { name: /^user management$/i })).toBeInTheDocument()
  })

  it('routes platform admin without selected tenant to dashboard tenant assist flow', () => {
    authState.isAuthenticated = true
    authState.user = { is_platform_admin: true }
    authState.tenantId = null
    authState.tenants = [{ id: 'tenant-1', role: 'viewer', name: 'Tenant One' }]

    renderApp('/dashboard')

    fireEvent.click(screen.getByRole('button', { name: /^user management$/i }))

    expect(screen.queryByText('Mock Admin Dashboard')).not.toBeInTheDocument()
    expect(screen.getByText(/select a tenant to continue to user management/i)).toBeInTheDocument()
  })

  it('auto-routes from dashboard to admin when pending intent exists and tenant is selected', () => {
    authState.isAuthenticated = true
    authState.user = { is_platform_admin: true }
    authState.tenantId = 'tenant-1'
    authState.tenants = [{ id: 'tenant-1', role: 'admin', name: 'Tenant One' }]

    renderApp({
      pathname: '/dashboard',
      state: {
        pendingAdminRoute: true,
        focusTenantSelector: true,
      },
    })

    expect(screen.getByText('Mock Admin Dashboard')).toBeInTheDocument()
  })

  it('renders admin dashboard when /admin is visited by authorized user', () => {
    authState.isAuthenticated = true
    authState.user = { is_platform_admin: true }
    authState.tenantId = 'tenant-1'
    authState.tenants = [{ id: 'tenant-1', role: 'viewer' }]

    renderApp('/admin')

    expect(screen.getByText('Mock Admin Dashboard')).toBeInTheDocument()
  })

  it('redirects away from /admin when unauthenticated', () => {
    renderApp('/admin')

    expect(screen.queryByText('Mock Admin Dashboard')).not.toBeInTheDocument()
    expect(screen.getByText(/welcome to ferrouslab authentication/i)).toBeInTheDocument()
  })
})
