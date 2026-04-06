/**
 * Tests for the ArtifactUpload component.
 *
 * Verifies:
 * 1. Renders upload prompt text.
 * 2. Shows accepted file extensions.
 * 3. Shows "Uploading…" text when isUploading is true.
 * 4. File input has the correct accept attribute.
 * 5. Calls onUpload when a file is selected via the input.
 */

import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { ArtifactUpload } from "@/components/artifacts/artifact-upload";

describe("ArtifactUpload", () => {
  it("renders upload prompt text", () => {
    const onUpload = jest.fn();
    render(<ArtifactUpload onUpload={onUpload} />);

    expect(
      screen.getByText("Drop files here or click to upload"),
    ).toBeInTheDocument();
  });

  it("shows accepted file extensions", () => {
    const onUpload = jest.fn();
    render(<ArtifactUpload onUpload={onUpload} />);

    expect(
      screen.getByText("Accepts .json, .yaml, .yml, .xml files"),
    ).toBeInTheDocument();
  });

  it('shows "Uploading…" text when isUploading is true', () => {
    const onUpload = jest.fn();
    render(<ArtifactUpload onUpload={onUpload} isUploading />);

    expect(screen.getByText("Uploading…")).toBeInTheDocument();
    expect(
      screen.queryByText("Drop files here or click to upload"),
    ).not.toBeInTheDocument();
  });

  it("file input has correct accept attribute", () => {
    const onUpload = jest.fn();
    const { container } = render(<ArtifactUpload onUpload={onUpload} />);

    const input = container.querySelector('input[type="file"]');
    expect(input).toHaveAttribute("accept", ".json,.yaml,.yml,.xml");
  });

  it("calls onUpload when a file is selected via input", () => {
    const onUpload = jest.fn();
    const { container } = render(<ArtifactUpload onUpload={onUpload} />);

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    expect(input).not.toBeNull();

    const testFile = new File(["test content"], "workflow.json", {
      type: "application/json",
    });

    fireEvent.change(input, { target: { files: [testFile] } });

    expect(onUpload).toHaveBeenCalledTimes(1);
    expect(onUpload).toHaveBeenCalledWith(testFile);
  });

  it("disables file input when isUploading is true", () => {
    const onUpload = jest.fn();
    const { container } = render(
      <ArtifactUpload onUpload={onUpload} isUploading />,
    );

    const input = container.querySelector('input[type="file"]');
    expect(input).toBeDisabled();
  });

  it("does not call onUpload when no file is selected", () => {
    const onUpload = jest.fn();
    const { container } = render(<ArtifactUpload onUpload={onUpload} />);

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [] } });

    expect(onUpload).not.toHaveBeenCalled();
  });
});
