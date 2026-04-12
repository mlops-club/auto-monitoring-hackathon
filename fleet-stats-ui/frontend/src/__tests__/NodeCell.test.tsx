import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import { NodeCell } from "../components/columns/NodeCell";

function wrap(ui: React.ReactElement) {
  return render(<table><tbody><tr>{ui}</tr></tbody></table>);
}

describe("NodeCell", () => {
  it("displays hostname and IP", () => {
    wrap(<NodeCell node={{ id: "node-1", ip: "10.0.0.1", health: "ok", labels: {} }} />);
    expect(screen.getByText("node-1")).toBeInTheDocument();
    expect(screen.getByText("10.0.0.1")).toBeInTheDocument();
  });

  it("shows labels tooltip on hover", async () => {
    const user = userEvent.setup();
    wrap(
      <NodeCell
        node={{ id: "n", ip: "1", health: "ok", labels: { "topology.kubernetes.io/zone": "us-west-2a" } }}
      />,
    );
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    await user.hover(screen.getByTestId("node-name"));
    expect(screen.getByRole("tooltip")).toHaveTextContent("topology.kubernetes.io/zone=us-west-2a");
  });
});
