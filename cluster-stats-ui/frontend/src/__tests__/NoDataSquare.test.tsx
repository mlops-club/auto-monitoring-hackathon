import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { NoDataSquare } from "../components/primitives/NoDataSquare";

describe("NoDataSquare", () => {
  it("renders with 'No data' accessible label", () => {
    render(<NoDataSquare />);
    expect(screen.getByLabelText("No data")).toBeInTheDocument();
  });
});
