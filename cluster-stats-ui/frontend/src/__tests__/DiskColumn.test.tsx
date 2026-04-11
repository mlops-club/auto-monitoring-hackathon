import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { DiskColumn } from "../components/columns/DiskColumn";
import type { DiskInfo } from "../api/types";

const disk = (overrides: Partial<DiskInfo> = {}): DiskInfo => ({
  dev: "nvme0", free: 50, iops: 200, maxIops: 500, tput: 0.1, maxTput: 0.25, totalTB: 1,
  ...overrides,
});

function wrap(ui: React.ReactElement) {
  return render(<table><tbody><tr>{ui}</tr></tbody></table>);
}

describe("DiskColumn", () => {
  it("renders one square per disk", () => {
    wrap(<DiskColumn disks={[disk({ dev: "a" }), disk({ dev: "b" })]} activeTab="Space" />);
    expect(screen.getAllByTestId("heat-square")).toHaveLength(2);
  });

  it("Space tab: fill reflects usage (100 - free)", () => {
    wrap(<DiskColumn disks={[disk({ free: 78 })]} activeTab="Space" />);
    expect(screen.getByTestId("heat-square-fill").style.height).toBe("22%");
  });

  it("IOPS tab: fill reflects iops/maxIops", () => {
    wrap(<DiskColumn disks={[disk({ iops: 250, maxIops: 500 })]} activeTab="IOPS" />);
    expect(screen.getByTestId("heat-square-fill").style.height).toBe("50%");
  });

  it("Tput tab: fill reflects tput/maxTput", () => {
    wrap(<DiskColumn disks={[disk({ tput: 0.125, maxTput: 0.25 })]} activeTab="Tput" />);
    expect(screen.getByTestId("heat-square-fill").style.height).toBe("50%");
  });

  it("0% free → 100% fill, red", () => {
    wrap(<DiskColumn disks={[disk({ free: 0 })]} activeTab="Space" />);
    const fill = screen.getByTestId("heat-square-fill");
    expect(fill.style.height).toBe("100%");
    expect(fill).toHaveClass("red");
  });

  it("100% free → 0% fill, green", () => {
    wrap(<DiskColumn disks={[disk({ free: 100 })]} activeTab="Space" />);
    const fill = screen.getByTestId("heat-square-fill");
    expect(fill.style.height).toBe("0%");
    expect(fill).toHaveClass("green");
  });

  it("renders empty when disks is empty", () => {
    wrap(<DiskColumn disks={[]} activeTab="Space" />);
    expect(screen.queryByTestId("heat-square")).not.toBeInTheDocument();
  });
});
