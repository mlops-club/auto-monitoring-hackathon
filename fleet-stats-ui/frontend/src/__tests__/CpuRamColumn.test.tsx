import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { CpuRamColumn } from "../components/columns/CpuRamColumn";

const cpu = { util: 35, cores: null as number | null, model: null as string | null };
const ram = { used: 42, total_bytes: 8e9, used_gb: 3.4, swap: 5 };

function wrap(ui: React.ReactElement) {
  return render(<table><tbody><tr>{ui}</tr></tbody></table>);
}

describe("CpuRamColumn", () => {
  it("CPU tab: heat square fill matches cpu.util", () => {
    wrap(<CpuRamColumn cpu={cpu} ram={ram} activeTab="CPU" />);
    const fills = screen.getAllByTestId("heat-square-fill");
    expect(fills[0].style.height).toBe("35%");
  });

  it("CPU tab: ram square fill matches ram.used", () => {
    wrap(<CpuRamColumn cpu={cpu} ram={ram} activeTab="CPU" />);
    const fills = screen.getAllByTestId("heat-square-fill");
    expect(fills[1].style.height).toBe("42%");
  });

  it("CPU tab: shows core count when available", () => {
    wrap(<CpuRamColumn cpu={{ ...cpu, cores: 128 }} ram={ram} activeTab="CPU" />);
    expect(screen.getByText("128c")).toBeInTheDocument();
  });

  it("Swap tab: renders swap square", () => {
    wrap(<CpuRamColumn cpu={cpu} ram={ram} activeTab="Swap" />);
    expect(screen.getByTestId("heat-square")).toBeInTheDocument();
  });

  it("0% CPU → empty green square", () => {
    wrap(<CpuRamColumn cpu={{ ...cpu, util: 0 }} ram={ram} activeTab="CPU" />);
    const fills = screen.getAllByTestId("heat-square-fill");
    expect(fills[0].style.height).toBe("0%");
    expect(fills[0]).toHaveClass("green");
  });

  it("100% CPU → full red square", () => {
    wrap(<CpuRamColumn cpu={{ ...cpu, util: 100 }} ram={ram} activeTab="CPU" />);
    const fills = screen.getAllByTestId("heat-square-fill");
    expect(fills[0].style.height).toBe("100%");
    expect(fills[0]).toHaveClass("red");
  });
});
