// @vitest-environment jsdom

import React from 'react'
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { MemoryRouter } from 'react-router-dom'
import App from './App'

const authState = {
  isAuthenticated: false,
  isLoading: false,
  logout: vi.fn(),
  user: null,
}

vi.mock('./auth_usermanagement', () => ({
  AUTH_CONFIG: {
    callbackPath: '/callback',
  },
  useAuth: () => authState,
  CustomSignupForm: ({ onConfirmed, onSwitchToLogin }) => (
    <div data-testid="signup-form">
      <button onClick={() => onConfirmed('test@example.com')}>Confirm Signup</button>
      <button onClick={onSwitchToLogin}>Switch to Login</button>
    </div>
  ),
  CustomLoginForm: ({ onSuccess, onSwitchToSignup, onForgotPassword }) => (
    <div data-testid="login-form">
      <button onClick={() => onSuccess()}>Login Success</button>
      <button onClick={onSwitchToSignup}>Switch to Signup</button>
      <button onClick={onForgotPassword}>Forgot Password</button>
    </div>
  ),
  ForgotPasswordForm: ({ onBackToLogin }) => (
    <div data-testid="forgot-password">
      <button onClick={onBackToLogin}>Back to Login</button>
    </div>
  ),
  AuthProvider: ({ children }) => <div>{children}</div>,
}))

vi.mock('./auth_usermanagement/services/cognitoClient', () => ({
  getHostedLoginUrl: vi.fn(async () => 'https://cognito.example.com/login'),
  appendIdentityProvider: vi.fn((url, provider) => `${url}?provider=${provider}`),
}))

vi.stubGlobal(
  'sessionStorage',
  new (class {
    data = {}
    getItem(key) {
      return this.data[key] || null
    }
    setItem(key, value) {
      this.data[key] = value
    }
    removeItem(key) {
      delete this.data[key]
    }
    clear() {
      this.data = {}
    }
  })(),
)

function renderApp(initialEntry = '/') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <App />
    </MemoryRouter>,
  )
}

describe('GrowthGorilla POC Routes', () => {
  beforeEach(() => {
    authState.isAuthenticated = false
    authState.isLoading = false
    authState.logout = vi.fn()
    authState.user = null
    sessionStorage.clear()
  })

  afterEach(() => {
    cleanup()
  })

  describe('Home Route', () => {
    it('redirects / to /splash/S1', () => {
      renderApp('/')
      expect(screen.getByText(/splash/i)).toBeInTheDocument()
    })
  })

  describe('Splash Route', () => {
    it('displays splash page for valid splash ID (S1)', () => {
      renderApp('/splash/S1')
      expect(screen.getByText(/splash s1/i)).toBeInTheDocument()
      expect(screen.getByText(/module.*a/i)).toBeInTheDocument()
    })

    it('displays splash page for all splash IDs (S1-S8)', () => {
      const splashIds = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8']
      splashIds.forEach((id) => {
        const { unmount } = renderApp(`/splash/${id}`)
        expect(screen.getByText(new RegExp(`splash ${id}`, 'i'))).toBeInTheDocument()
        unmount()
      })
    })

    it('maps S1-S2 to module_a', () => {
      renderApp('/splash/S1')
      expect(screen.getByText(/module.*a/i)).toBeInTheDocument()
      cleanup()

      renderApp('/splash/S2')
      expect(screen.getByText(/module.*a/i)).toBeInTheDocument()
    })

    it('maps S3-S4 to module_b', () => {
      renderApp('/splash/S3')
      expect(screen.getByText(/module.*b/i)).toBeInTheDocument()
      cleanup()

      renderApp('/splash/S4')
      expect(screen.getByText(/module.*b/i)).toBeInTheDocument()
    })

    it('maps S5-S6 to module_c', () => {
      renderApp('/splash/S5')
      expect(screen.getByText(/module.*c/i)).toBeInTheDocument()
      cleanup()

      renderApp('/splash/S6')
      expect(screen.getByText(/module.*c/i)).toBeInTheDocument()
    })

    it('maps S7-S8 to module_d', () => {
      renderApp('/splash/S7')
      expect(screen.getByText(/module.*d/i)).toBeInTheDocument()
      cleanup()

      renderApp('/splash/S8')
      expect(screen.getByText(/module.*d/i)).toBeInTheDocument()
    })

    it('contains Continue to Wheel and Skip to Signup buttons', () => {
      renderApp('/splash/S1')
      expect(screen.getByRole('button', { name: /wheel/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /signup/i })).toBeInTheDocument()
    })
  })

  describe('Wheel Route', () => {
    it('displays wheel page with spin button', () => {
      renderApp('/wheel')
      expect(screen.getByRole('button', { name: /spin/i })).toBeInTheDocument()
    })

    it('shows offer options (1 month free, $20 off, 20% off)', () => {
      renderApp('/wheel')
      const pageText = screen.getByText(/month.*free|dollar.*off|percent.*off/i, {
        selector: 'div',
      })
      expect(pageText).toBeInTheDocument()
    })

    it('contains navigation to signup only', () => {
      renderApp('/wheel')
      expect(screen.getByRole('button', { name: /signup/i })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: /sign up/i })).toBeInTheDocument()
    })
  })

  describe('Signup Route', () => {
    it('displays signup form', () => {
      renderApp('/signup')
      expect(screen.getByTestId('signup-form')).toBeInTheDocument()
    })

    it('redirects authenticated users to purchase', () => {
      authState.isAuthenticated = true
      renderApp('/signup')
      expect(screen.getByText(/payment|purchase/i)).toBeInTheDocument()
    })

    it('shows funnel banner when context exists', async () => {
      sessionStorage.setItem(
        'gg_funnel_context_v1',
        JSON.stringify({
          splashId: 'S1',
          moduleTarget: 'module_a',
          offer: { code: 'ONE_MONTH_FREE', label: '1 month free' },
        }),
      )
      renderApp('/signup')
      await waitFor(() => {
        expect(screen.getByText(/journey context/i)).toBeInTheDocument()
        expect(screen.getByText(/1 month free/i)).toBeInTheDocument()
      })
    })
  })

  describe('Login Route', () => {
    it('redirects /login to signup', () => {
      renderApp('/login')
      expect(screen.getByTestId('signup-form')).toBeInTheDocument()
    })
  })

  describe('Callback Route', () => {
    it('shows callback completion message for unauthenticated users', () => {
      authState.isAuthenticated = false
      renderApp('/callback')
      expect(screen.getByText(/completing sign-in/i)).toBeInTheDocument()
    })

    it('redirects authenticated users to purchase', () => {
      authState.isAuthenticated = true
      renderApp('/callback')
      expect(screen.getByText(/payment|purchase/i)).toBeInTheDocument()
    })
  })

  describe('Onboarding Route', () => {
    it('displays onboarding page when authenticated', () => {
      authState.isAuthenticated = true
      renderApp('/onboarding')
      expect(screen.getByText(/onboarding/i)).toBeInTheDocument()
    })

    it('allows unauthenticated users to view onboarding page in mock flow', () => {
      authState.isAuthenticated = false
      renderApp('/onboarding')
      expect(screen.getByText(/onboarding|welcome aboard/i)).toBeInTheDocument()
    })

    it('contains buttons to finish onboarding, restart funnel, and sign out', () => {
      authState.isAuthenticated = true
      renderApp('/onboarding')
      expect(screen.getByRole('button', { name: /finish|continue/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /restart/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /sign out/i })).toBeInTheDocument()
    })
  })

  describe('Dashboard Route', () => {
    it('redirects /dashboard to onboarding', () => {
      authState.isAuthenticated = true
      renderApp('/dashboard')
      expect(screen.getByText(/onboarding|welcome aboard/i)).toBeInTheDocument()
    })

    it('redirects /dashboard to onboarding for unauthenticated users too', () => {
      authState.isAuthenticated = false
      renderApp('/dashboard')
      expect(screen.getByText(/onboarding|welcome aboard/i)).toBeInTheDocument()
    })
  })

  describe('Navigation', () => {
    it('header contains navigation links', () => {
      renderApp('/')
      expect(screen.getByRole('link', { name: /splash|home/i })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: /wheel/i })).toBeInTheDocument()
    })

    it('unauthenticated header shows signup but no login link', () => {
      authState.isAuthenticated = false
      renderApp('/')
      expect(screen.getByRole('link', { name: /signup/i })).toBeInTheDocument()
      expect(screen.queryByRole('link', { name: /login/i })).not.toBeInTheDocument()
    })

    it('authenticated header shows sign out button', () => {
      authState.isAuthenticated = true
      renderApp('/')
      expect(screen.getByRole('button', { name: /sign out/i })).toBeInTheDocument()
    })
  })

  describe('FunnelBanner Component', () => {
    it('displays context summary when session data exists', async () => {
      sessionStorage.setItem(
        'gg_funnel_context_v1',
        JSON.stringify({
          splashId: 'S5',
          moduleTarget: 'module_c',
          offer: { code: 'TWENTY_PERCENT_OFF_FULL', label: '20% off full modules' },
        }),
      )
      authState.isAuthenticated = true
      renderApp('/onboarding')
      await waitFor(() => {
        expect(screen.getByText(/journey context/i)).toBeInTheDocument()
        expect(screen.getByText(/S5/)).toBeInTheDocument()
        expect(screen.getByText(/module_c/)).toBeInTheDocument()
        expect(screen.getByText(/20%.*off/i)).toBeInTheDocument()
      })
    })

    it('does not display banner when no context exists', () => {
      authState.isAuthenticated = true
      renderApp('/onboarding')
      const banners = document.querySelectorAll('[style*="background"]')
      expect(banners.length).toBeLessThan(2) // Only header background
    })
  })

  describe('Session Storage Persistence', () => {
    it('persists funnel context across page navigations', () => {
      sessionStorage.setItem(
        'gg_funnel_context_v1',
        JSON.stringify({
          splashId: 'S3',
          moduleTarget: 'module_b',
          offer: { code: 'ONE_MONTH_FREE', label: '1 month free' },
        }),
      )

      // Navigate to onboarding
      const { rerender } = renderApp('/onboarding')
      expect(sessionStorage.getItem('gg_funnel_context_v1')).toBeTruthy()

      // Navigate to different page
      rerender(
        <MemoryRouter initialEntries={['/wheel']}>
          <App />
        </MemoryRouter>,
      )

      // Context should still exist
      expect(sessionStorage.getItem('gg_funnel_context_v1')).toBeTruthy()
      const stored = JSON.parse(sessionStorage.getItem('gg_funnel_context_v1'))
      expect(stored.splashId).toBe('S3')
    })
  })
})
