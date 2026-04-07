/**
 * Tests for the ProjectList component.
 *
 * Verifies:
 * 1. Shows empty state when no projects exist.
 * 2. Renders project cards with project names.
 * 3. Renders project descriptions when present.
 * 4. Shows artifact count for each project.
 * 5. Links each card to the project detail page.
 */

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

jest.mock("@/components/ui/card", () => ({
  Card: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => (
    <div data-testid="card" className={className}>
      {children}
    </div>
  ),
  CardHeader: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  CardTitle: ({ children }: { children: React.ReactNode }) => (
    <h3>{children}</h3>
  ),
  CardDescription: ({ children }: { children: React.ReactNode }) => (
    <p>{children}</p>
  ),
  CardContent: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

import React from "react";
import { render, screen } from "@testing-library/react";
import { ProjectList } from "@/components/projects/project-list";
import type { Project } from "@/hooks/use-projects";

function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: "proj-001",
    name: "Test Project",
    description: null,
    status: "active",
    artifactCount: 3,
    graphVersion: 1,
    createdBy: "user-001",
    createdByName: "Test User",
    createdAt: "2024-06-15T10:00:00Z",
    updatedBy: null,
    updatedByName: null,
    updatedAt: "2024-06-15T10:00:00Z",
    ...overrides,
  };
}

describe("ProjectList", () => {
  it("shows empty state when no projects exist", () => {
    render(<ProjectList projects={[]} />);

    expect(
      screen.getByText(
        "No projects yet. Create your first project to get started.",
      ),
    ).toBeInTheDocument();
  });

  it("renders project cards with project names", () => {
    const projects = [
      makeProject({ id: "p1", name: "Alpha Project" }),
      makeProject({ id: "p2", name: "Beta Project" }),
    ];

    render(<ProjectList projects={projects} />);

    expect(screen.getByText("Alpha Project")).toBeInTheDocument();
    expect(screen.getByText("Beta Project")).toBeInTheDocument();
  });

  it("renders project descriptions when present", () => {
    const projects = [
      makeProject({
        id: "p1",
        name: "Described Project",
        description: "A detailed description",
      }),
    ];

    render(<ProjectList projects={projects} />);

    expect(screen.getByText("A detailed description")).toBeInTheDocument();
  });

  it("does not render description paragraph when description is null", () => {
    const projects = [
      makeProject({ id: "p1", name: "No Desc", description: null }),
    ];

    render(<ProjectList projects={projects} />);

    expect(
      screen.queryByText("A detailed description"),
    ).not.toBeInTheDocument();
  });

  it("shows artifact count for each project", () => {
    const projects = [
      makeProject({ id: "p1", name: "Proj A", artifactCount: 5 }),
      makeProject({ id: "p2", name: "Proj B", artifactCount: 1 }),
    ];

    render(<ProjectList projects={projects} />);

    expect(screen.getByText("5 artifacts")).toBeInTheDocument();
    expect(screen.getByText("1 artifact")).toBeInTheDocument();
  });

  it("links each card to the project detail page", () => {
    const projects = [
      makeProject({ id: "proj-abc", name: "Linked" }),
    ];

    render(<ProjectList projects={projects} />);

    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/dashboard/projects/proj-abc");
  });

  it("renders multiple project cards", () => {
    const projects = [
      makeProject({ id: "p1", name: "One" }),
      makeProject({ id: "p2", name: "Two" }),
      makeProject({ id: "p3", name: "Three" }),
    ];

    render(<ProjectList projects={projects} />);

    const cards = screen.getAllByTestId("card");
    expect(cards).toHaveLength(3);
  });
});
