import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import { HeatSquare } from "../components/primitives/HeatSquare";

const tt = { title: "Test", rows: [{ label: "Val", value: "50%" }] };

describe("HeatSquare", () => {
  it("renders with correct fill height", () => {
    render(<HeatSquare value={45} tooltip={tt} />);
    const fill = screen.getByTestId("heat-square-fill");
    expect(fill.style.height).toBe("45%");
  });

  it("green when value < 40", () => {
    render(<HeatSquare value={25} tooltip={tt} />);
    expect(screen.getByTestId("heat-square-fill")).toHaveClass("green");
  });

  it("yellow when value >= 40 and < 70", () => {
    render(<HeatSquare value={55} tooltip={tt} />);
    expect(screen.getByTestId("heat-square-fill")).toHaveClass("yellow");
  });

  it("red when value >= 70", () => {
    render(<HeatSquare value={85} tooltip={tt} />);
    expect(screen.getByTestId("heat-square-fill")).toHaveClass("red");
  });

  it("shows tooltip on hover with title and rows", async () => {
    const user = userEvent.setup();
    const tip = { title: "CPU", rows: [{ label: "Util", value: "50%" }] };
    render(<HeatSquare value={50} tooltip={tip} />);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    await user.hover(screen.getByTestId("heat-square"));
    const tooltip = screen.getByRole("tooltip");
    expect(tooltip).toHaveTextContent("CPU");
    expect(tooltip).toHaveTextContent("Util");
    expect(tooltip).toHaveTextContent("50%");
  });

  it("clamps fill height to 0-100", () => {
    const { rerender } = render(<HeatSquare value={-10} tooltip={tt} />);
    expect(screen.getByTestId("heat-square-fill").style.height).toBe("0%");
    rerender(<HeatSquare value={150} tooltip={tt} />);
    expect(screen.getByTestId("heat-square-fill").style.height).toBe("100%");
  });
});
