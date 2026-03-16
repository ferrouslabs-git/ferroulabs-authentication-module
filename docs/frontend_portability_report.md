# Frontend Portability Report

Date: 2026-03-16
Scope: frontend auth/usermanagement module portability for host apps with custom UI.

## Executive Summary

The frontend module is now portable enough to reuse across host apps if you treat it as an authentication and tenant-management runtime layer, not as a fixed visual design system.

The safest model is:
- Ship the auth runtime core as required.
- Ship UI components/pages as optional starter assets.
- Let each host app own routing shell, layout, and visual design.

## Portability Status

Portable and host-agnostic now:
- Config-driven auth paths and namespace.
- Config-driven callback and invite routes.
- Token/session handling via module APIs.
- Tenant-aware permission checks (tenant role + platform admin support).
- Admin route wiring patterns and no-tenant fallback UX.

Still host-owned by design:
- App shell layout and navigation.
- Brand/theme/typography.
- Route placement and information architecture.
- Final admin UX copy and interaction style.

## What To Ship

Required runtime package (ship these):
- frontend/src/auth_usermanagement/config.js
- frontend/src/auth_usermanagement/context/AuthProvider.jsx
- frontend/src/auth_usermanagement/hooks/*
- frontend/src/auth_usermanagement/services/authApi.js
- frontend/src/auth_usermanagement/services/cognitoClient.js
- frontend/src/auth_usermanagement/constants/*
- frontend/src/auth_usermanagement/utils/*
- frontend/src/auth_usermanagement/index.js

Optional UI starter package (ship if useful as scaffolding):
- frontend/src/auth_usermanagement/components/*
- frontend/src/auth_usermanagement/pages/AdminDashboard.jsx
- frontend/src/auth_usermanagement/pages/index.js

Host-side wiring examples to ship as snippets:
- frontend/src/main.jsx provider wiring pattern.
- frontend/src/App.jsx route mounting pattern for callback, invite, dashboard, admin.

## What Not To Ship As Mandatory

Do not force host apps to keep these unchanged:
- Sidebar/shell visuals.
- Dashboard look and page copy.
- Admin page visual hierarchy.
- Button styles, spacing, and motion.

These should be considered replaceable UI adapters over a stable auth runtime.

## Host Integration Contract (Frontend)

Host app owns:
- Browser router setup.
- Global layout and navigation.
- Theme and CSS system.
- Where auth pages are mounted.

Module owns:
- Auth state machine and token lifecycle.
- Cognito callback/token exchange glue.
- Tenant-aware API client behavior.
- Permission and role checks.
- Invite accept and user-management request flows.

## Required Environment Configuration

Set these per host app:
- VITE_AUTH_NAMESPACE
- VITE_AUTH_API_BASE_PATH
- VITE_AUTH_CALLBACK_PATH
- VITE_AUTH_INVITE_PATH_PREFIX

Acceptance checks:
- Callback route resolves correctly.
- Invite route resolves correctly.
- Auth API base path points to host backend prefix.

## Minimum Acceptance Test Matrix For New Host

Auth flow:
- Sign in and sign up redirects work.
- Callback completes and user context loads.
- Logout clears local/module state.

Tenant flow:
- Tenant selection persists in module state.
- No-tenant state shows guidance instead of broken actions.

Admin flow:
- Admin entry visibility matches role rules.
- Platform admin without tenant gets tenant-select assist.
- After tenant selection, admin route opens successfully.
- Invite, role update, remove, suspend, unsuspend operations hit backend with tenant headers.

Regression:
- Frontend tests pass.
- Production build passes.

## Packaging Recommendation

Recommended practical approach now:
- Keep copy-paste module reuse for speed.
- Version by git tags/releases in this repository.
- Keep a short CHANGELOG section for frontend module breaking changes.

Recommended later:
- Split into a package with a stable public API surface.
- Expose headless hooks/services package and optional UI package separately.

## Ship Checklist

Before shipping to a new host:
- Confirm backend auth prefix in host and frontend base path match.
- Confirm callback and invite route paths are configured.
- Confirm provider wiring exists at app root.
- Confirm admin route gating works for tenant admin and platform admin.
- Confirm no-tenant states are user-friendly and actionable.
- Run test suite and production build.

## Current Recommendation

You can ship now with confidence if you ship the runtime core as required and treat all visual UI as host-customizable.

For your stated goal (new app, different UI), keep the runtime contract fixed and rebuild host-facing pages around your new design system.
