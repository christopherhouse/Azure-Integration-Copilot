import { render, screen } from "@testing-library/react";
import Home from "@/app/page";

describe("Home page", () => {
  it("renders the application title", () => {
    render(<Home />);
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent("Integration Copilot");
  });

  it("renders the description text", () => {
    render(<Home />);
    expect(
      screen.getByText(
        "Azure Integration Services management and analysis platform"
      )
    ).toBeInTheDocument();
  });
});
