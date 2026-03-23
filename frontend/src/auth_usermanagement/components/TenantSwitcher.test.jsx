// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import { TenantSwitcher } from "./TenantSwitcher";

const tenantState = {
  tenantId: "t-1",
  tenants: [
    { id: "t-1", name: "Acme", role: "admin" },
    { id: "t-2", name: "Beta", role: "member" },
  ],
  changeTenant: vi.fn(),
};

vi.mock("../hooks/useTenant", () => ({
  useTenant: () => tenantState,
}));

afterEach(() => cleanup());

beforeEach(() => {
  vi.clearAllMocks();
});

describe("TenantSwitcher", () => {
  it("renders a select with all tenants", () => {
    render(<TenantSwitcher />);
    const select = screen.getByRole("combobox");
    expect(select).toBeInTheDocument();
    expect(select.value).toBe("t-1");

    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(2);
    expect(options[0]).toHaveTextContent("Acme (admin)");
    expect(options[1]).toHaveTextContent("Beta (member)");
  });

  it("calls changeTenant on selection change", () => {
    render(<TenantSwitcher />);
    const select = screen.getByRole("combobox");
    fireEvent.change(select, { target: { value: "t-2" } });
    expect(tenantState.changeTenant).toHaveBeenCalledWith("t-2");
  });

  it("renders custom label", () => {
    render(<TenantSwitcher label="Workspace" />);
    expect(screen.getByText("Workspace:")).toBeInTheDocument();
  });

  it("renders nothing when no tenants", () => {
    tenantState.tenants = [];
    const { container } = render(<TenantSwitcher />);
    expect(container.innerHTML).toBe("");
    // Restore
    tenantState.tenants = [
      { id: "t-1", name: "Acme", role: "admin" },
      { id: "t-2", name: "Beta", role: "member" },
    ];
  });
});
