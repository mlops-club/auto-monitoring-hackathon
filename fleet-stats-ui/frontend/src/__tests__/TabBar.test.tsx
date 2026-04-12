import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { TabBar } from "../components/primitives/TabBar";

describe("TabBar", () => {
  it("renders tabs and highlights the active one", () => {
    render(<TabBar tabs={["Space", "IOPS", "Tput"]} active="Space" onChange={() => {}} />);
    expect(screen.getByText("Space")).toHaveClass("active");
    expect(screen.getByText("IOPS")).not.toHaveClass("active");
  });

  it("calls onChange when a tab is clicked", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<TabBar tabs={["Space", "IOPS"]} active="Space" onChange={onChange} />);
    await user.click(screen.getByText("IOPS"));
    expect(onChange).toHaveBeenCalledWith("IOPS");
  });
});
