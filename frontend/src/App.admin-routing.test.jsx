// @vitest-environment jsdom

import React from 'react'
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
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

  it('does not show legacy User Management nav button for authenticated users', () => {
    authState.isAuthenticated = true
    authState.user = { is_platform_admin: false }
    authState.tenantId = 'tenant-1'
    authState.tenants = [{ id: 'tenant-1', role: 'admin' }]

    renderApp('/dashboard')

    expect(screen.queryByRole('button', { name: /^user management$/i })).not.toBeInTheDocument()
    expect(screen.getByText(/welcome aboard/i)).toBeInTheDocument()
  })

  it('keeps User Management nav hidden for authenticated tenant members', () => {
    authState.isAuthenticated = true
    authState.user = { is_platform_admin: false }
    authState.tenantId = 'tenant-1'
    authState.tenants = [{ id: 'tenant-1', role: 'member' }]

    renderApp('/dashboard')

    expect(screen.queryByRole('button', { name: /^user management$/i })).not.toBeInTheDocument()
    expect(screen.getByText(/welcome aboard/i)).toBeInTheDocument()
  })

  it('keeps User Management nav hidden for platform admin without selected tenant', () => {
    authState.isAuthenticated = true
    authState.user = { is_platform_admin: true }
    authState.tenantId = null
    authState.tenants = [{ id: 'tenant-1', role: 'viewer', name: 'Tenant One' }]

    renderApp('/dashboard')

    expect(screen.queryByRole('button', { name: /^user management$/i })).not.toBeInTheDocument()
    expect(screen.getByText(/welcome aboard/i)).toBeInTheDocument()
  })

  it('routes /dashboard to onboarding instead of legacy admin dashboard', () => {
    authState.isAuthenticated = true
    authState.user = { is_platform_admin: true }
    authState.tenantId = null
    authState.tenants = [{ id: 'tenant-1', role: 'viewer', name: 'Tenant One' }]

    renderApp('/dashboard')

    expect(screen.queryByText('Mock Admin Dashboard')).not.toBeInTheDocument()
    expect(screen.getByText(/welcome aboard/i)).toBeInTheDocument()
  })

  it('ignores legacy pending admin intent and keeps dashboard on onboarding', () => {
    authState.isAuthenticated = true
    authState.user = { is_platform_admin: true }
    authState.tenantId = 'tenant-1'
    authState.tenants = [{ id: 'tenant-1', role: 'admin', name: 'Tenant One' }]

    renderApp('/dashboard')

    expect(screen.queryByText('Mock Admin Dashboard')).not.toBeInTheDocument()
    expect(screen.getByText(/welcome aboard/i)).toBeInTheDocument()
  })

  it('redirects /admin to splash flow for authenticated users', () => {
    authState.isAuthenticated = true
    authState.user = { is_platform_admin: true }
    authState.tenantId = 'tenant-1'
    authState.tenants = [{ id: 'tenant-1', role: 'viewer' }]

    renderApp('/admin')

    expect(screen.queryByText('Mock Admin Dashboard')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /accelerate your growth/i })).toBeInTheDocument()
  })

  it('redirects /admin to splash flow for unauthenticated users', () => {
    renderApp('/admin')

    expect(screen.queryByText('Mock Admin Dashboard')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /accelerate your growth/i })).toBeInTheDocument()
  })
})
