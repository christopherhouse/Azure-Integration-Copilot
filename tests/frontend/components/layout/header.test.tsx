import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockSignOut = jest.fn();
const mockUseSession = jest.fn();
jest.mock("next-auth/react", () => ({
  signOut: mockSignOut,
  useSession: mockUseSession,
}));

const mockUseUser = jest.fn();
jest.mock("@/hooks/use-user", () => ({
  useUser: mockUseUser,
}));

const mockUseGravatarUrl = jest.fn();
jest.mock("@/hooks/use-gravatar", () => ({
  useGravatarUrl: mockUseGravatarUrl,
}));

jest.mock("@/components/layout/breadcrumbs", () => ({
  Breadcrumbs: () => <nav data-testid="breadcrumbs">Breadcrumbs</nav>,
}));

jest.mock("@/components/ui/avatar", () => ({
  Avatar: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => (
    <div data-testid="avatar" className={className}>
      {children}
    </div>
  ),
  AvatarImage: ({ src, alt }: { src: string; alt?: string }) => (
    <img data-testid="avatar-image" src={src} alt={alt} />
  ),
  AvatarFallback: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => (
    <span data-testid="avatar-fallback" className={className}>
      {children}
    </span>
  ),
}));

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

// Lucide icons
jest.mock("lucide-react", () => ({
  LogOut: (props: Record<string, unknown>) => (
    <svg data-testid="icon-logout" {...props} />
  ),
}));

import { Header } from "@/components/layout/header";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function setupDefaults(overrides?: {
  userName?: string | null;
  email?: string | null;
  gravatarUrl?: string;
}) {
  const userName = overrides?.userName ?? "Alice Smith";
  const email = overrides?.email ?? "alice@example.com";
  const gravatarUrl = overrides?.gravatarUrl ?? "https://gravatar.com/alice";

  mockUseSession.mockReturnValue({
    data: {
      user: { name: userName, email },
    },
  });
  mockUseUser.mockReturnValue({ data: { email, gravatarEmail: null } });
  mockUseGravatarUrl.mockReturnValue(gravatarUrl);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Header", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setupDefaults();
  });

  it("renders breadcrumbs", () => {
    render(<Header />);
    expect(screen.getByTestId("breadcrumbs")).toBeInTheDocument();
  });

  it("shows user name from session", () => {
    render(<Header />);
    expect(screen.getByText("Alice Smith")).toBeInTheDocument();
  });

  it("renders avatar with fallback initials", () => {
    render(<Header />);
    // The component takes the first char of the name and uppercases it
    expect(screen.getByTestId("avatar-fallback")).toHaveTextContent("A");
  });

  it("sign out button calls signOut with callbackUrl", () => {
    render(<Header />);

    const signOutBtn = screen.getByLabelText("Sign out");
    fireEvent.click(signOutBtn);

    expect(mockSignOut).toHaveBeenCalledTimes(1);
    expect(mockSignOut).toHaveBeenCalledWith({ callbackUrl: "/login" });
  });
});
