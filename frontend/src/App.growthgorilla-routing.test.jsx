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
    it('shows flow chooser at /', () => {
      renderApp('/')
      expect(screen.getByText(/choose your route/i)).toBeInTheDocument()
      expect(screen.getAllByRole('link', { name: /^normal route$/i }).length).toBeGreaterThan(0)
      expect(screen.getAllByRole('link', { name: /^splash route$/i }).length).toBeGreaterThan(0)
    })
  })

  describe('Splash Route', () => {
    it('displays splash page for valid splash ID (S1)', () => {
      renderApp('/splash/S1')
      expect(screen.getByRole('heading', { name: /accelerate your growth/i })).toBeInTheDocument()
      expect(screen.getByText(/module.*a/i)).toBeInTheDocument()
    })

    it('displays splash page for all splash IDs (S1-S8)', () => {
      const splashIdsToModuleText = {
        S1: /module.*a/i,
        S2: /module.*a/i,
        S3: /module.*b/i,
        S4: /module.*b/i,
        S5: /module.*c/i,
        S6: /module.*c/i,
        S7: /module.*d/i,
        S8: /module.*d/i,
      }

      Object.entries(splashIdsToModuleText).forEach(([id, moduleRegex]) => {
        const { unmount } = renderApp(`/splash/${id}`)
        expect(screen.getByText(/spin the wheel to unlock an exclusive offer/i)).toBeInTheDocument()
        expect(screen.getByText(moduleRegex)).toBeInTheDocument()
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

    it('contains links to wheel and signup', () => {
      renderApp('/splash/S1')
      expect(screen.getByRole('link', { name: /spin the wheel/i })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: /skip to sign up/i })).toBeInTheDocument()
    })
  })

  describe('Wheel Route', () => {
    it('displays wheel page with spin button', () => {
      renderApp('/wheel')
      expect(screen.getByRole('button', { name: /spin/i })).toBeInTheDocument()
    })

    it('shows offer options (1 month free, $20 off, 20% off)', () => {
      renderApp('/wheel')
      expect(screen.getAllByText(/1 month free/i).length).toBeGreaterThan(0)
      expect(screen.getAllByText(/\$20\s*off/i).length).toBeGreaterThan(0)
      expect(screen.getAllByText(/20%\s*off/i).length).toBeGreaterThan(0)
    })

    it('contains navigation to signup only', () => {
      renderApp('/wheel')
      expect(screen.getByRole('link', { name: /go to sign up|sign up/i })).toBeInTheDocument()
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
      expect(screen.getByRole('heading', { name: /complete your purchase/i })).toBeInTheDocument()
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
    it('renders login form at /login', () => {
      renderApp('/login')
      expect(screen.getByTestId('login-form')).toBeInTheDocument()
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
      expect(screen.getByRole('heading', { name: /complete your purchase/i })).toBeInTheDocument()
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
      expect(screen.getByText(/^welcome aboard$/i)).toBeInTheDocument()
    })

    it('contains buttons to finish onboarding, explore offers, and sign out', () => {
      authState.isAuthenticated = true
      renderApp('/onboarding')
      expect(screen.getByRole('button', { name: /finish|continue/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /explore other offers/i })).toBeInTheDocument()
      expect(screen.getAllByRole('button', { name: /sign out/i }).length).toBeGreaterThan(0)
    })
  })

  describe('Dashboard Route', () => {
    it('redirects /dashboard to onboarding', () => {
      authState.isAuthenticated = true
      renderApp('/dashboard')
      expect(screen.getByText(/^welcome aboard$/i)).toBeInTheDocument()
    })

    it('redirects /dashboard to onboarding for unauthenticated users too', () => {
      authState.isAuthenticated = false
      renderApp('/dashboard')
      expect(screen.getByText(/^welcome aboard$/i)).toBeInTheDocument()
    })
  })

  describe('Navigation', () => {
    it('header contains navigation links', () => {
      renderApp('/')
      expect(screen.getByRole('link', { name: /^home$/i })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: /^wheel$/i })).toBeInTheDocument()
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
      expect(screen.queryByText(/journey context:/i)).not.toBeInTheDocument()
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
