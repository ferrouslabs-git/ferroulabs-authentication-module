// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

// ── Mocks ───────────────────────────────────────────────────────

const navigateMock = vi.fn();

vi.mock("react-router-dom", () => ({
  useParams: () => ({ token: "invite-tok-abc" }),
  useNavigate: () => navigateMock,
}));

const authState = {
  user: null,
  token: null,
  refreshAuthState: vi.fn(),
};

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => authState,
}));

const apiMocks = vi.hoisted(() => ({
  getInvitationDetails: vi.fn(),
  acceptInvitation: vi.fn(),
}));

vi.mock("../services/authApi", () => apiMocks);

vi.mock("./LoginForm", () => ({
  LoginForm: () => <div data-testid="login-form">LoginForm</div>,
}));

// Import component AFTER mocks
import { AcceptInvitation } from "./AcceptInvitation";

afterEach(() => cleanup());

beforeEach(() => {
  vi.clearAllMocks();
  authState.user = null;
  authState.token = null;
  localStorage.clear();
});

describe("AcceptInvitation", () => {
  it("shows loading state initially", () => {
    apiMocks.getInvitationDetails.mockReturnValue(new Promise(() => {})); // never resolves
    render(<AcceptInvitation />);
    expect(screen.getByText("Loading invitation...")).toBeInTheDocument();
  });

  it("shows error when invitation is invalid", async () => {
    apiMocks.getInvitationDetails.mockRejectedValue({
      response: { data: { detail: "Invitation not found" } },
    });

    render(<AcceptInvitation />);
    await waitFor(() => {
      expect(screen.getByText("Invitation not found")).toBeInTheDocument();
    });
  });

  it("shows expired state", async () => {
    apiMocks.getInvitationDetails.mockResolvedValue({
      tenant_name: "Acme",
      email: "test@example.com",
      role: "member",
      is_expired: true,
      is_accepted: false,
    });

    render(<AcceptInvitation />);
    await waitFor(() => {
      expect(screen.getByText("Invitation Expired", { exact: false })).toBeInTheDocument();
    });
  });

  it("shows already-accepted state", async () => {
    apiMocks.getInvitationDetails.mockResolvedValue({
      tenant_name: "Acme",
      email: "test@example.com",
      role: "member",
      is_expired: false,
      is_accepted: true,
    });

    render(<AcceptInvitation />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Already Accepted/ })).toBeInTheDocument();
    });
  });

  it("shows login form when user is not authenticated", async () => {
    apiMocks.getInvitationDetails.mockResolvedValue({
      tenant_name: "Acme",
      email: "test@example.com",
      role: "member",
      is_expired: false,
      is_accepted: false,
    });

    render(<AcceptInvitation />);
    await waitFor(() => {
      expect(screen.getByTestId("login-form")).toBeInTheDocument();
      expect(screen.getByText("You've Been Invited!", { exact: false })).toBeInTheDocument();
    });
  });

  it("saves post-login redirect for unauthenticated user", async () => {
    apiMocks.getInvitationDetails.mockResolvedValue({
      tenant_name: "Acme",
      email: "test@example.com",
      role: "member",
      is_expired: false,
      is_accepted: false,
    });

    render(<AcceptInvitation />);
    await waitFor(() => {
      expect(localStorage.getItem("authum_post_login_redirect")).toBeTruthy();
    });
  });

  it("shows email mismatch warning when emails differ", async () => {
    authState.user = { email: "other@example.com" };
    authState.token = "tok-1";

    apiMocks.getInvitationDetails.mockResolvedValue({
      tenant_name: "Acme",
      email: "test@example.com",
      role: "member",
      is_expired: false,
      is_accepted: false,
    });

    render(<AcceptInvitation />);
    await waitFor(() => {
      expect(screen.getByText("Email Mismatch", { exact: false })).toBeInTheDocument();
    });
  });

  it("shows accept button when user matches invitation email", async () => {
    authState.user = { email: "test@example.com" };
    authState.token = "tok-1";

    apiMocks.getInvitationDetails.mockResolvedValue({
      tenant_name: "Acme",
      email: "test@example.com",
      role: "member",
      is_expired: false,
      is_accepted: false,
    });

    render(<AcceptInvitation />);
    await waitFor(() => {
      expect(screen.getByText("Accept Invitation")).toBeInTheDocument();
    });
  });

  it("calls acceptInvitation and navigates on success", async () => {
    authState.user = { email: "test@example.com" };
    authState.token = "tok-1";

    apiMocks.getInvitationDetails.mockResolvedValue({
      tenant_name: "Acme",
      email: "test@example.com",
      role: "member",
      is_expired: false,
      is_accepted: false,
    });
    apiMocks.acceptInvitation.mockResolvedValue({ message: "ok" });

    render(<AcceptInvitation />);
    await waitFor(() => {
      expect(screen.getByText("Accept Invitation")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Accept Invitation"));

    await waitFor(() => {
      expect(apiMocks.acceptInvitation).toHaveBeenCalledWith("tok-1", "invite-tok-abc");
      expect(authState.refreshAuthState).toHaveBeenCalled();
      expect(navigateMock).toHaveBeenCalledWith("/", { replace: true });
    });
  });

  it("shows error when accept fails", async () => {
    authState.user = { email: "test@example.com" };
    authState.token = "tok-1";

    apiMocks.getInvitationDetails.mockResolvedValue({
      tenant_name: "Acme",
      email: "test@example.com",
      role: "member",
      is_expired: false,
      is_accepted: false,
    });
    apiMocks.acceptInvitation.mockRejectedValue({
      response: { data: { detail: "Email mismatch" } },
    });

    render(<AcceptInvitation />);
    await waitFor(() => screen.getByText("Accept Invitation"));

    fireEvent.click(screen.getByText("Accept Invitation"));

    await waitFor(() => {
      expect(screen.getByText("Email mismatch")).toBeInTheDocument();
    });
  });
});
