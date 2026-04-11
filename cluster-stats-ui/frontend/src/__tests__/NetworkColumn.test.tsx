import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { NetworkColumn } from "../components/columns/NetworkColumn";
import type { NicInfo } from "../api/types";

const nic = (overrides: Partial<NicInfo> = {}): NicInfo => ({
  dev: "eth0", bw: 50, drops: 0, tx: 1, rx: 2,
  ...overrides,
});

function wrap(ui: React.ReactElement) {
  return render(<table><tbody><tr>{ui}</tr></tbody></table>);
}

describe("NetworkColumn", () => {
  it("renders one square per NIC", () => {
    wrap(<NetworkColumn nics={[nic({ dev: "a" }), nic({ dev: "b" })]} activeTab="BW" />);
    expect(screen.getAllByTestId("heat-square")).toHaveLength(2);
  });

  it("BW tab: fill reflects bandwidth percent", () => {
    wrap(<NetworkColumn nics={[nic({ bw: 50 })]} activeTab="BW" />);
    expect(screen.getByTestId("heat-square-fill").style.height).toBe("50%");
  });

  it("Drops tab: 0 drops → green (0%)", () => {
    wrap(<NetworkColumn nics={[nic({ drops: 0 })]} activeTab="Drops" />);
    expect(screen.getByTestId("heat-square-fill")).toHaveClass("green");
  });

  it("Drops tab: >500 drops → red (100%)", () => {
    wrap(<NetworkColumn nics={[nic({ drops: 1247 })]} activeTab="Drops" />);
    expect(screen.getByTestId("heat-square-fill")).toHaveClass("red");
  });

  it("renders empty when nics is empty", () => {
    wrap(<NetworkColumn nics={[]} activeTab="BW" />);
    expect(screen.queryByTestId("heat-square")).not.toBeInTheDocument();
  });
});
