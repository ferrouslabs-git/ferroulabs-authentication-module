/**
 * GrowthGorilla POC Theme & Styles
 * Brand colors and typography for the funnel POC
 */

export const theme = {
  // Primary color palette
  colors: {
    primary: '#0f766e',      // Teal - Primary CTA
    primaryLight: '#14b8a6', // Light Teal - Hover/accent
    primaryDark: '#0a2c38',  // Dark Teal - Headings
    secondary: '#134b5f',    // Dark blue-gray - Secondary text
    accent: '#9dc7d6',       // Light blue - Borders/dividers
    success: '#10b981',      // Green - Success states
    warning: '#f59e0b',      // Amber - Warning states
    background: '#ffffff',
    surface: '#f9fafb',      // Light gray background
    border: '#e5e7eb',       // Light gray border
    text: {
      primary: '#111827',
      secondary: '#6b7280',
      tertiary: '#9ca3af',
    },
  },

  // Typography
  fonts: {
    family: {
      base: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Oxygen", "Ubuntu", "Cantarell", "Fira Sans", "Droid Sans", "Helvetica Neue", sans-serif',
      display: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", sans-serif',
    },
    sizes: {
      xs: 12,
      sm: 14,
      base: 16,
      lg: 18,
      xl: 20,
      '2xl': 24,
      '3xl': 30,
      '4xl': 36,
    },
    weights: {
      regular: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
    },
  },

  // Spacing
  spacing: {
    xs: 4,
    sm: 8,
    md: 12,
    lg: 16,
    xl: 20,
    '2xl': 24,
    '3xl': 32,
    '4xl': 40,
  },

  // Border radius
  radius: {
    sm: 4,
    md: 8,
    lg: 12,
    xl: 16,
    full: 999,
  },

  // Shadows
  shadows: {
    sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
    md: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
    lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
    xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
  },

  // Transitions
  transitions: {
    fast: 'all 150ms cubic-bezier(0.4, 0, 0.2, 1)',
    base: 'all 300ms cubic-bezier(0.4, 0, 0.2, 1)',
    slow: 'all 500ms cubic-bezier(0.4, 0, 0.2, 1)',
  },
}

// Common component styles
export const componentStyles = {
  page: {
    maxWidth: 900,
    margin: '0 auto',
    padding: `${theme.spacing['4xl']}px ${theme.spacing.lg}px`,
    fontFamily: theme.fonts.family.base,
  },

  container: {
    maxWidth: 1200,
    margin: '0 auto',
    padding: `0 ${theme.spacing.lg}px`,
  },

  hero: {
    textAlign: 'center',
    marginBottom: theme.spacing['3xl'],
  },

  kicker: {
    margin: 0,
    color: theme.colors.primary,
    fontWeight: theme.fonts.weights.bold,
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
    fontSize: theme.fonts.sizes.xs,
    marginBottom: theme.spacing.xs,
  },

  heading: {
    fontSize: theme.fonts.sizes['4xl'],
    fontWeight: theme.fonts.weights.bold,
    color: theme.colors.primaryDark,
    margin: `${theme.spacing.md}px 0 ${theme.spacing.lg}px`,
    lineHeight: 1.2,
  },

  subheading: {
    fontSize: theme.fonts.sizes.xl,
    fontWeight: theme.fonts.weights.semibold,
    color: theme.colors.secondary,
    margin: `${theme.spacing.md}px 0`,
    lineHeight: 1.4,
  },

  body: {
    fontSize: theme.fonts.sizes.base,
    color: theme.colors.text.secondary,
    lineHeight: 1.6,
    marginBottom: theme.spacing.lg,
  },

  button: {
    padding: `${theme.spacing.md}px ${theme.spacing.lg}px`,
    borderRadius: theme.radius.lg,
    fontSize: theme.fonts.sizes.base,
    fontWeight: theme.fonts.weights.semibold,
    border: 'none',
    cursor: 'pointer',
    transition: theme.transitions.base,
    fontFamily: theme.fonts.family.base,
  },

  buttonPrimary: {
    background: theme.colors.primary,
    color: '#fff',
    boxShadow: theme.shadows.md,
    '&:hover': {
      background: theme.colors.primaryLight,
      boxShadow: theme.shadows.lg,
    },
  },

  buttonSecondary: {
    background: 'transparent',
    color: theme.colors.primary,
    border: `2px solid ${theme.colors.primary}`,
    '&:hover': {
      background: `${theme.colors.primary}10`,
    },
  },

  buttonOutline: {
    background: 'transparent',
    color: theme.colors.text.secondary,
    border: `1px solid ${theme.colors.border}`,
    '&:hover': {
      background: theme.colors.surface,
      borderColor: theme.colors.primary,
    },
  },

  link: {
    color: theme.colors.primary,
    textDecoration: 'none',
    fontWeight: theme.fonts.weights.semibold,
    transition: theme.transitions.fast,
    '&:hover': {
      color: theme.colors.primaryLight,
      textDecoration: 'underline',
    },
  },

  card: {
    background: theme.colors.background,
    border: `1px solid ${theme.colors.border}`,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.xl,
    boxShadow: theme.shadows.sm,
    transition: theme.transitions.base,
    '&:hover': {
      boxShadow: theme.shadows.md,
    },
  },

  badge: {
    display: 'inline-block',
    padding: `${theme.spacing.xs}px ${theme.spacing.md}px`,
    borderRadius: theme.radius.full,
    fontSize: theme.fonts.sizes.xs,
    fontWeight: theme.fonts.weights.semibold,
    background: theme.colors.surface,
    color: theme.colors.secondary,
  },
}
