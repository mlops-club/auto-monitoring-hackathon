import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { GpuColumn } from "../components/columns/GpuColumn";
import { RdmaColumn } from "../components/columns/RdmaColumn";
import { PcieColumn } from "../components/columns/PcieColumn";

function wrap(ui: React.ReactElement) {
  return render(<table><tbody><tr>{ui}</tr></tbody></table>);
}

describe("Stub columns", () => {
  it("GpuColumn renders NoDataSquare when gpus=null", () => {
    wrap(<GpuColumn gpus={null} />);
    expect(screen.getByLabelText("No data")).toBeInTheDocument();
  });

  it("RdmaColumn renders NoDataSquare when rdma=null", () => {
    wrap(<RdmaColumn rdma={null} />);
    expect(screen.getByLabelText("No data")).toBeInTheDocument();
  });

  it("PcieColumn renders NoDataSquare when pcie=null", () => {
    wrap(<PcieColumn pcie={null} />);
    expect(screen.getByLabelText("No data")).toBeInTheDocument();
  });
});
