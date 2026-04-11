import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { CpuRamColumn } from "../components/columns/CpuRamColumn";

const cpu = { util: 35, cores: 128, model: "AMD EPYC 9654" };
const ram = { used: 42, total: "2 TB", usedGb: 860, swap: 5, psi: 1.2 };

function wrap(ui: React.ReactElement) {
  return render(<table><tbody><tr>{ui}</tr></tbody></table>);
}

describe("CpuRamColumn", () => {
  it("CPU tab: shows core count", () => {
    wrap(<CpuRamColumn cpu={cpu} ram={ram} activeTab="CPU" />);
    expect(screen.getByText("128c")).toBeInTheDocument();
  });

  it("CPU tab: heat square fill matches cpu.util", () => {
    wrap(<CpuRamColumn cpu={cpu} ram={ram} activeTab="CPU" />);
    const fills = screen.getAllByTestId("heat-square-fill");
    expect(fills[0].style.height).toBe("35%");
  });

  it("CPU tab: ram square fill matches ram.used", () => {
    wrap(<CpuRamColumn cpu={cpu} ram={ram} activeTab="CPU" />);
    const fills = screen.getAllByTestId("heat-square-fill");
    // Second square is RAM
    expect(fills[1].style.height).toBe("42%");
  });

  it("Swap tab: renders two squares (swap + PSI)", () => {
    wrap(<CpuRamColumn cpu={cpu} ram={ram} activeTab="Swap" />);
    expect(screen.getAllByTestId("heat-square")).toHaveLength(2);
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
