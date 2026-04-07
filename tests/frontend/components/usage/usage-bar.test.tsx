/**
 * Tests for the UsageBar component.
 *
 * Verifies:
 * 1. Renders text showing used/limit counts.
 * 2. Shows the computed percentage.
 * 3. Renders a progressbar with correct ARIA attributes.
 * 4. Green bar color when usage is below 70%.
 * 5. Yellow bar color when usage is 70–89%.
 * 6. Red bar color when usage is ≥ 90%.
 * 7. Handles limit of 0 without division-by-zero.
 * 8. Caps the percentage at 100% when used > limit.
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import { UsageBar } from "@/components/usage/usage-bar";

describe("UsageBar", () => {
  it("renders text showing used/limit counts", () => {
    render(<UsageBar used={3} limit={10} />);

    expect(screen.getByText("3 of 10 daily analyses used")).toBeInTheDocument();
  });

  it("shows computed percentage", () => {
    render(<UsageBar used={3} limit={10} />);

    expect(screen.getByText("30%")).toBeInTheDocument();
  });

  it("renders progressbar with correct aria attributes", () => {
    render(<UsageBar used={5} limit={20} />);

    const progressbar = screen.getByRole("progressbar");
    expect(progressbar).toHaveAttribute("aria-valuenow", "5");
    expect(progressbar).toHaveAttribute("aria-valuemin", "0");
    expect(progressbar).toHaveAttribute("aria-valuemax", "20");
    expect(progressbar).toHaveAttribute(
      "aria-label",
      "5 of 20 daily analyses used",
    );
  });

  it("applies green color when usage is below 70%", () => {
    const { container } = render(<UsageBar used={6} limit={10} />);

    const innerBar = container.querySelector("[style]");
    expect(innerBar).toHaveClass("bg-emerald-500");
    expect(innerBar).not.toHaveClass("bg-yellow-500");
    expect(innerBar).not.toHaveClass("bg-red-500");
  });

  it("applies yellow color when usage is 70–89%", () => {
    const { container } = render(<UsageBar used={7} limit={10} />);

    const innerBar = container.querySelector("[style]");
    expect(innerBar).toHaveClass("bg-yellow-500");
    expect(innerBar).not.toHaveClass("bg-emerald-500");
    expect(innerBar).not.toHaveClass("bg-red-500");
  });

  it("applies yellow color at exactly 89%", () => {
    const { container } = render(<UsageBar used={89} limit={100} />);

    const innerBar = container.querySelector("[style]");
    expect(innerBar).toHaveClass("bg-yellow-500");
  });

  it("applies red color when usage is 90% or higher", () => {
    const { container } = render(<UsageBar used={9} limit={10} />);

    const innerBar = container.querySelector("[style]");
    expect(innerBar).toHaveClass("bg-red-500");
    expect(innerBar).not.toHaveClass("bg-emerald-500");
    expect(innerBar).not.toHaveClass("bg-yellow-500");
  });

  it("applies red color at exactly 90%", () => {
    const { container } = render(<UsageBar used={90} limit={100} />);

    const innerBar = container.querySelector("[style]");
    expect(innerBar).toHaveClass("bg-red-500");
  });

  it("handles limit of 0 without division by zero", () => {
    render(<UsageBar used={5} limit={0} />);

    expect(screen.getByText("0%")).toBeInTheDocument();
    expect(screen.getByText("5 of 0 daily analyses used")).toBeInTheDocument();

    const progressbar = screen.getByRole("progressbar");
    expect(progressbar).toHaveAttribute("aria-valuemax", "0");
  });

  it("caps percentage at 100% when used exceeds limit", () => {
    const { container } = render(<UsageBar used={15} limit={10} />);

    expect(screen.getByText("100%")).toBeInTheDocument();

    const innerBar = container.querySelector("[style]");
    expect(innerBar).toHaveStyle({ width: "100%" });
  });
});
