import React from "react";
import { render, screen } from "@testing-library/react";

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

const mockUseProject = jest.fn();
jest.mock("@/hooks/use-projects", () => ({
  useProject: mockUseProject,
}));

// Lucide icons
jest.mock("lucide-react", () => ({
  ChevronRight: (props: Record<string, unknown>) => (
    <svg data-testid="chevron-right" {...props} />
  ),
}));

import { Breadcrumbs } from "@/components/layout/breadcrumbs";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Breadcrumbs", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseProject.mockReturnValue({ data: undefined, isLoading: false });
  });

  it('renders "Home" for /dashboard', () => {
    mockUsePathname.mockReturnValue("/dashboard");
    render(<Breadcrumbs />);

    expect(screen.getByText("Home")).toBeInTheDocument();
  });

  it('renders "Home > Settings" for /dashboard/settings', () => {
    mockUsePathname.mockReturnValue("/dashboard/settings");
    render(<Breadcrumbs />);

    expect(screen.getByText("Home")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it('renders "Home > Projects" for /dashboard/projects', () => {
    mockUsePathname.mockReturnValue("/dashboard/projects");
    render(<Breadcrumbs />);

    expect(screen.getByText("Home")).toBeInTheDocument();
    expect(screen.getByText("Projects")).toBeInTheDocument();
  });

  it("replaces projectId with project name when loaded", () => {
    const projectId = "abc-def-123";
    mockUsePathname.mockReturnValue(`/dashboard/projects/${projectId}`);
    mockUseProject.mockReturnValue({
      data: { name: "My Cool Project" },
      isLoading: false,
    });

    render(<Breadcrumbs />);

    expect(screen.getByText("My Cool Project")).toBeInTheDocument();
    expect(screen.queryByText(projectId)).not.toBeInTheDocument();
  });

  it('shows "…" while project name is loading', () => {
    const projectId = "abc-def-456";
    mockUsePathname.mockReturnValue(`/dashboard/projects/${projectId}`);
    mockUseProject.mockReturnValue({
      data: undefined,
      isLoading: true,
    });

    render(<Breadcrumbs />);

    expect(screen.getByText("…")).toBeInTheDocument();
    expect(screen.getByLabelText("Loading project name")).toBeInTheDocument();
  });
});
