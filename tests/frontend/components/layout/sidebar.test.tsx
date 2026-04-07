import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockUsePathname = jest.fn();
jest.mock("next/navigation", () => ({
  usePathname: mockUsePathname,
}));

jest.mock("next/link", () => {
  return ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
    [key: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  );
});

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    ...props
  }: {
    children: React.ReactNode;
    onClick?: () => void;
    [key: string]: unknown;
  }) => (
    <button onClick={onClick} {...props}>
      {children}
    </button>
  ),
}));

// Lucide icons – render as simple SVGs with a recognisable test-id
jest.mock("lucide-react", () => ({
  FolderKanban: (props: Record<string, unknown>) => (
    <svg data-testid="icon-folder-kanban" {...props} />
  ),
  Settings: (props: Record<string, unknown>) => (
    <svg data-testid="icon-settings" {...props} />
  ),
  PanelLeftClose: (props: Record<string, unknown>) => (
    <svg data-testid="icon-panel-left-close" {...props} />
  ),
  PanelLeft: (props: Record<string, unknown>) => (
    <svg data-testid="icon-panel-left" {...props} />
  ),
  ShieldCheck: (props: Record<string, unknown>) => (
    <svg data-testid="icon-shield-check" {...props} />
  ),
}));

// cn – identity passthrough
jest.mock("@/lib/utils", () => ({
  cn: (...args: unknown[]) => args.filter(Boolean).join(" "),
}));

import { Sidebar } from "@/components/layout/sidebar";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Sidebar", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUsePathname.mockReturnValue("/dashboard");
  });

  it("renders brand name 'Integrisight.ai'", () => {
    render(<Sidebar />);
    expect(screen.getByText("Integrisight.ai")).toBeInTheDocument();
  });

  it("renders Projects and Settings nav links", () => {
    render(<Sidebar />);

    const projectsLink = screen.getByText("Projects").closest("a");
    const settingsLink = screen.getByText("Settings").closest("a");

    expect(projectsLink).toHaveAttribute("href", "/dashboard");
    expect(settingsLink).toHaveAttribute("href", "/dashboard/settings");
  });

  it("highlights Projects when pathname is /dashboard", () => {
    mockUsePathname.mockReturnValue("/dashboard");
    render(<Sidebar />);

    const projectsLink = screen.getByText("Projects").closest("a");
    expect(projectsLink?.className).toContain("bg-sidebar-accent");
  });

  it("highlights Settings when pathname is /dashboard/settings", () => {
    mockUsePathname.mockReturnValue("/dashboard/settings");
    render(<Sidebar />);

    const settingsLink = screen.getByText("Settings").closest("a");
    expect(settingsLink?.className).toContain("bg-sidebar-accent");

    // Projects should NOT be highlighted (avoid matching "bg-sidebar-accent/50")
    const projectsLink = screen.getByText("Projects").closest("a");
    expect(projectsLink?.className).toMatch(/hover:bg-sidebar-accent\/50/);
    expect(projectsLink?.className).not.toMatch(/bg-sidebar-accent(?!\/)/);
  });

  it("highlights Projects when on a project page (/dashboard/projects/xxx)", () => {
    mockUsePathname.mockReturnValue("/dashboard/projects/abc-123");
    render(<Sidebar />);

    const projectsLink = screen.getByText("Projects").closest("a");
    expect(projectsLink?.className).toContain("bg-sidebar-accent");
  });

  it("renders Privacy & Security link", () => {
    render(<Sidebar />);

    const privacyLink = screen.getByText("Privacy & Security").closest("a");
    expect(privacyLink).toHaveAttribute("href", "/privacy");
  });

  it("collapse button hides text labels", () => {
    render(<Sidebar />);

    // All labels should be visible initially
    expect(screen.getByText("Integrisight.ai")).toBeInTheDocument();
    expect(screen.getByText("Projects")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
    expect(screen.getByText("Privacy & Security")).toBeInTheDocument();

    // Click the collapse button
    const collapseBtn = screen.getByLabelText("Collapse sidebar");
    fireEvent.click(collapseBtn);

    // Labels should be hidden after collapse
    expect(screen.queryByText("Integrisight.ai")).not.toBeInTheDocument();
    expect(screen.queryByText("Projects")).not.toBeInTheDocument();
    expect(screen.queryByText("Settings")).not.toBeInTheDocument();
    expect(screen.queryByText("Privacy & Security")).not.toBeInTheDocument();
  });
});
