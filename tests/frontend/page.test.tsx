/* eslint-disable @typescript-eslint/no-explicit-any */
const mockRedirect = jest.fn();
jest.mock("next/navigation", () => ({
  redirect: (url: string) => {
    mockRedirect(url);
    throw new Error("NEXT_REDIRECT");
  },
}));

const mockGetServerSession = jest.fn();
jest.mock("next-auth", () => ({
  getServerSession: (...args: any[]) => mockGetServerSession(...args),
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

    await expect(Home()).rejects.toThrow("NEXT_REDIRECT");
    expect(mockRedirect).toHaveBeenCalledWith("/login");
  });

  it("redirects to /dashboard when there is an active session", async () => {
    mockGetServerSession.mockResolvedValue({ user: { name: "Test" } });

    await expect(Home()).rejects.toThrow("NEXT_REDIRECT");
    expect(mockRedirect).toHaveBeenCalledWith("/dashboard");
  });
});
