const REDIRECT_ERROR = "NEXT_REDIRECT";

const mockRedirect = jest.fn();
jest.mock("next/navigation", () => ({
  redirect: (url: string) => {
    mockRedirect(url);
    throw new Error(REDIRECT_ERROR);
  },
}));

const mockGetServerSession = jest.fn();
jest.mock("next-auth", () => ({
  getServerSession: mockGetServerSession,
}));

jest.mock("@/lib/auth", () => ({
  authOptions: {},
}));

import Home from "@/app/page";

describe("Home page", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("redirects to /login when there is no session", async () => {
    mockGetServerSession.mockResolvedValue(null);

    await expect(Home()).rejects.toThrow(REDIRECT_ERROR);
    expect(mockRedirect).toHaveBeenCalledWith("/login");
  });

  it("redirects to /dashboard when there is an active session", async () => {
    mockGetServerSession.mockResolvedValue({ user: { name: "Test" } });

    await expect(Home()).rejects.toThrow(REDIRECT_ERROR);
    expect(mockRedirect).toHaveBeenCalledWith("/dashboard");
  });
});
