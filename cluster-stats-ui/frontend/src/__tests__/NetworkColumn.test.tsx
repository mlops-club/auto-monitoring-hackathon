import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { NetworkColumn } from "../components/columns/NetworkColumn";
import type { NicMetrics } from "../api/types";

const nic = (overrides: Partial<NicMetrics> = {}): NicMetrics => ({
  dev: "eth0", bw_bytes: 62500000, speed_bytes: 125000000, drops: 0,
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
    // 62.5M / 125M = 50%
    wrap(<NetworkColumn nics={[nic()]} activeTab="BW" />);
    expect(screen.getByTestId("heat-square-fill").style.height).toBe("50%");
  });

  it("Drops tab: 0 drops → green", () => {
    wrap(<NetworkColumn nics={[nic({ drops: 0 })]} activeTab="Drops" />);
    expect(screen.getByTestId("heat-square-fill")).toHaveClass("green");
  });

  it("Drops tab: >500 drops → red", () => {
    wrap(<NetworkColumn nics={[nic({ drops: 1247 })]} activeTab="Drops" />);
    expect(screen.getByTestId("heat-square-fill")).toHaveClass("red");
  });

  it("renders empty when nics is empty", () => {
    wrap(<NetworkColumn nics={[]} activeTab="BW" />);
    expect(screen.queryByTestId("heat-square")).not.toBeInTheDocument();
  });
});
