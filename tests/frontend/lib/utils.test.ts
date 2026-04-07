/**
 * Tests for the `cn` utility in @/lib/utils.
 *
 * Verifies that:
 * 1. Returns empty string when called with no arguments.
 * 2. Merges multiple class name strings.
 * 3. Filters out undefined, null, and false values.
 * 4. Resolves conflicting Tailwind utility classes (last wins).
 * 5. Handles conditional classes via arrays and objects.
 */

import { cn } from "@/lib/utils";

describe("cn", () => {
  it("returns empty string for no arguments", () => {
    expect(cn()).toBe("");
  });

  it("returns a single class unchanged", () => {
    expect(cn("px-4")).toBe("px-4");
  });

  it("merges multiple class strings", () => {
    const result = cn("font-bold", "text-red-500");
    expect(result).toContain("font-bold");
    expect(result).toContain("text-red-500");
  });

  it("handles undefined values gracefully", () => {
    expect(cn("px-4", undefined)).toBe("px-4");
  });

  it("handles null values gracefully", () => {
    expect(cn("px-4", null)).toBe("px-4");
  });

  it("handles false values gracefully", () => {
    expect(cn("px-4", false)).toBe("px-4");
  });

  it("handles a mix of falsy values", () => {
    expect(cn(undefined, "mt-2", null, false, "mb-4")).toBe("mt-2 mb-4");
  });

  it("merges conflicting Tailwind padding classes (last wins)", () => {
    expect(cn("px-4", "px-2")).toBe("px-2");
  });

  it("merges conflicting Tailwind margin classes (last wins)", () => {
    expect(cn("mt-4", "mt-8")).toBe("mt-8");
  });

  it("merges conflicting Tailwind text-color classes (last wins)", () => {
    expect(cn("text-red-500", "text-blue-500")).toBe("text-blue-500");
  });

  it("handles conditional classes via objects", () => {
    const isActive = true;
    const isDisabled = false;
    const result = cn({ "bg-blue-500": isActive, "opacity-50": isDisabled });
    expect(result).toBe("bg-blue-500");
  });

  it("handles conditional classes via arrays", () => {
    const result = cn(["px-4", "py-2"]);
    expect(result).toContain("px-4");
    expect(result).toContain("py-2");
  });

  it("handles nested arrays", () => {
    const result = cn(["px-4", ["py-2", "mt-1"]]);
    expect(result).toContain("px-4");
    expect(result).toContain("py-2");
    expect(result).toContain("mt-1");
  });

  it("combines objects and strings", () => {
    const result = cn("base-class", { "active-class": true, "hidden-class": false });
    expect(result).toContain("base-class");
    expect(result).toContain("active-class");
    expect(result).not.toContain("hidden-class");
  });
});
