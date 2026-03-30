const mockSignIn = jest.fn();
jest.mock("next-auth/react", () => ({
  signIn: mockSignIn,
}));

import { render, screen, fireEvent } from "@testing-library/react";
import LoginPage from "@/app/(auth)/login/page";

describe("LoginPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("production mode", () => {
    const originalEnv = process.env.NODE_ENV;

    beforeAll(() => {
      Object.defineProperty(process.env, "NODE_ENV", { value: "production", writable: true });
    });

    afterAll(() => {
      Object.defineProperty(process.env, "NODE_ENV", { value: originalEnv, writable: true });
    });

    it("renders the sign-in button", () => {
      render(<LoginPage />);
      expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
    });

    it("calls signIn with 'azure-ad' provider and dashboard callbackUrl", () => {
      render(<LoginPage />);
      fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
      expect(mockSignIn).toHaveBeenCalledWith("azure-ad", { callbackUrl: "/dashboard" });
    });
  });
});
