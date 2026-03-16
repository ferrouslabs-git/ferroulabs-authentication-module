// @vitest-environment jsdom

import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'

import { UserList } from './UserList'

const authState = {
  token: 'fake-token',
  tenantId: null,
  user: {
    id: 'current-admin-id',
    is_platform_admin: true,
  },
}

const roleState = {
  role: null,
}

const toast = {
  success: vi.fn(),
  error: vi.fn(),
}

const mockUsers = [
  {
    user_id: 'current-admin-id',
    email: 'current-admin@example.com',
    name: 'Current Admin',
    is_platform_admin: true,
    is_active: true,
    updated_at: '2026-03-16T10:00:00Z',
    memberships: [],
  },
  {
    user_id: 'regular-user-id',
    email: 'regular-user@example.com',
    name: 'Regular User',
    is_platform_admin: false,
    is_active: true,
    updated_at: '2026-03-16T10:00:00Z',
    memberships: [],
  },
  {
    user_id: 'other-admin-id',
    email: 'other-admin@example.com',
    name: 'Other Admin',
    is_platform_admin: true,
    is_active: true,
    updated_at: '2026-03-16T10:00:00Z',
    memberships: [],
  },
]

const apiMocks = vi.hoisted(() => ({
  getPlatformUsers: vi.fn(),
  getTenantUsers: vi.fn(),
  promotePlatformUser: vi.fn(),
  demotePlatformUser: vi.fn(),
  updateTenantUserRole: vi.fn(),
  removeTenantUser: vi.fn(),
  suspendUser: vi.fn(),
  unsuspendUser: vi.fn(),
}))

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => authState,
}))

vi.mock('../hooks/useRole', () => ({
  useRole: () => roleState,
}))

vi.mock('./Toast', () => ({
  useToast: () => toast,
}))

vi.mock('../services/authApi', () => apiMocks)

vi.mock('../constants/permissions', () => ({
  PERMISSIONS: {
    REMOVE_USERS: 'remove_users',
    SUSPEND_USERS: 'suspend_users',
  },
  checkPermission: (user) => Boolean(user?.is_platform_admin),
}))

vi.mock('./RoleSelector', () => ({
  RoleSelector: () => <div>Mock Role Selector</div>,
}))

function renderUserList() {
  return render(
    <UserList mode="platform" canManage={true} />,
  )
}

describe('UserList platform admin actions', () => {
  beforeEach(() => {
    apiMocks.getPlatformUsers.mockReset()
    apiMocks.getTenantUsers.mockReset()
    apiMocks.promotePlatformUser.mockReset()
    apiMocks.demotePlatformUser.mockReset()
    apiMocks.updateTenantUserRole.mockReset()
    apiMocks.removeTenantUser.mockReset()
    apiMocks.suspendUser.mockReset()
    apiMocks.unsuspendUser.mockReset()
    toast.success.mockReset()
    toast.error.mockReset()

    apiMocks.getPlatformUsers.mockResolvedValue(mockUsers)
    apiMocks.promotePlatformUser.mockResolvedValue({ message: 'ok' })
    apiMocks.demotePlatformUser.mockResolvedValue({ message: 'ok' })
  })

  it('promotes a regular user to super admin from the platform directory', async () => {
    renderUserList()

    expect(await screen.findByText('regular-user@example.com')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /grant super admin to regular-user@example.com/i }))
    fireEvent.click(screen.getByRole('button', { name: /^grant$/i }))

    await waitFor(() => {
      expect(apiMocks.promotePlatformUser).toHaveBeenCalledWith('fake-token', 'regular-user-id')
    })

    expect(toast.success).toHaveBeenCalled()
  })

  it('demotes another super admin from the platform directory', async () => {
    renderUserList()

    expect(await screen.findByText('other-admin@example.com')).toBeInTheDocument()

    fireEvent.click(screen.getAllByRole('button', { name: /remove super admin from other-admin@example.com/i })[0])
    fireEvent.click(screen.getByRole('button', { name: /^remove$/i }))

    await waitFor(() => {
      expect(apiMocks.demotePlatformUser).toHaveBeenCalledWith('fake-token', 'other-admin-id')
    })

    expect(toast.success).toHaveBeenCalled()
  })
})