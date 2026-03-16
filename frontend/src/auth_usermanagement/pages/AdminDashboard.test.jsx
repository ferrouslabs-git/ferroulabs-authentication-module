// @vitest-environment jsdom

import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { MemoryRouter } from 'react-router-dom'
import { AdminDashboard } from './AdminDashboard'

const mockNavigate = vi.fn()
const authState = {
  user: null,
  tenantId: null,
}
const roleState = {
  role: null,
}

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => authState,
}))

vi.mock('../hooks/useRole', () => ({
  useRole: () => roleState,
}))

vi.mock('../components/UserList', () => ({
  UserList: () => <div>Mock User List</div>,
}))

vi.mock('../components/InviteUserModal', () => ({
  InviteUserModal: () => <div>Mock Invite Modal</div>,
}))

vi.mock('../constants/permissions', () => ({
  PERMISSIONS: {
    REMOVE_USERS: 'remove_users',
    INVITE_USERS: 'invite_users',
  },
  checkPermission: (user, permission, role) => {
    if (!user) return false
    if (user.is_platform_admin) return true
    if (!role) return false
    if (permission === 'remove_users' || permission === 'invite_users') {
      return role === 'owner' || role === 'admin'
    }
    return false
  },
}))

function renderPage() {
  return render(
    <MemoryRouter>
      <AdminDashboard />
    </MemoryRouter>,
  )
}

describe('AdminDashboard No-Tenant UX', () => {
  beforeEach(() => {
    authState.user = null
    authState.tenantId = null
    roleState.role = null
    mockNavigate.mockReset()
  })

  it('shows platform-admin select-tenant guidance when no tenant is selected', () => {
    authState.user = { is_platform_admin: true }
    authState.tenantId = null

    renderPage()

    expect(screen.getByText(/select a tenant to manage users/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /go to dashboard/i })).toBeInTheDocument()
  })

  it('shows membership guidance for non-platform users without tenant', () => {
    authState.user = { is_platform_admin: false }
    authState.tenantId = null
    roleState.role = null

    renderPage()

    expect(screen.getByText(/you don't have any tenant memberships yet/i)).toBeInTheDocument()
  })
})
