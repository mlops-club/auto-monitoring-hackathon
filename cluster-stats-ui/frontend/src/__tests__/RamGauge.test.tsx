import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { RamGauge } from "../components/primitives/RamGauge";

describe("RamGauge", () => {
  it("renders gauge with correct height and label", () => {
    render(<RamGauge percent={45} label="3.6 / 8 GB" />);
    const fill = screen.getByTestId("ram-gauge-fill");
    expect(fill.style.height).toBe("45%");
    expect(screen.getByTestId("ram-gauge")).toHaveAttribute("title", "3.6 / 8 GB");
    expect(screen.getByText("45%")).toBeInTheDocument();
  });
});
