import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ClusterDashboard } from "../components/ClusterDashboard";
import { MOCK_NODES, MOCK_LABELS } from "../api/mock-data";

vi.mock("../api/client", () => ({
  fetchNodes: vi.fn(),
  fetchLabels: vi.fn(),
}));

import { fetchNodes, fetchLabels } from "../api/client";

const mockFetchNodes = vi.mocked(fetchNodes);
const mockFetchLabels = vi.mocked(fetchLabels);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ClusterDashboard", () => {
  it("renders one NodeRow per node", async () => {
    mockFetchNodes.mockResolvedValue(MOCK_NODES);
    mockFetchLabels.mockResolvedValue(MOCK_LABELS);
    render(<ClusterDashboard />);
    await waitFor(() => {
      expect(screen.getAllByTestId("node-row")).toHaveLength(3);
    });
  });

  it("shows loading state before data arrives", () => {
    mockFetchNodes.mockReturnValue(new Promise(() => {})); // never resolves
    mockFetchLabels.mockReturnValue(new Promise(() => {}));
    render(<ClusterDashboard />);
    expect(screen.getByTestId("loading")).toBeInTheDocument();
  });

  it("shows error banner when fetch fails", async () => {
    mockFetchNodes.mockRejectedValue(new Error("Network error"));
    mockFetchLabels.mockResolvedValue(MOCK_LABELS);
    render(<ClusterDashboard />);
    await waitFor(() => {
      expect(screen.getByTestId("error-banner")).toHaveTextContent("Network error");
    });
  });

  it("handles empty node list", async () => {
    mockFetchNodes.mockResolvedValue({ nodes: [] });
    mockFetchLabels.mockResolvedValue({ nodes: {} });
    render(<ClusterDashboard />);
    await waitFor(() => {
      expect(screen.getByTestId("no-nodes")).toBeInTheDocument();
    });
  });

  it("disk tab switching is global (all rows update)", async () => {
    mockFetchNodes.mockResolvedValue(MOCK_NODES);
    mockFetchLabels.mockResolvedValue(MOCK_LABELS);
    const user = userEvent.setup();
    render(<ClusterDashboard />);

    await waitFor(() => screen.getAllByTestId("node-row"));

    // Get the IOPS tab in the header (the first tab-bar with IOPS)
    const iopsTabs = screen.getAllByText("IOPS");
    await user.click(iopsTabs[0]);

    // All disk columns should still render (just with different values)
    const diskColumns = screen.getAllByTestId("disk-column");
    expect(diskColumns.length).toBeGreaterThan(0);
  });

  it("shows header with node count", async () => {
    mockFetchNodes.mockResolvedValue(MOCK_NODES);
    mockFetchLabels.mockResolvedValue(MOCK_LABELS);
    render(<ClusterDashboard />);
    await waitFor(() => {
      expect(screen.getByTestId("dashboard-header")).toHaveTextContent("3 nodes");
    });
  });

  it("group-by renders group headers", async () => {
    mockFetchNodes.mockResolvedValue(MOCK_NODES);
    mockFetchLabels.mockResolvedValue(MOCK_LABELS);
    const user = userEvent.setup();
    render(<ClusterDashboard />);

    await waitFor(() => screen.getAllByTestId("node-row"));

    await user.selectOptions(screen.getByTestId("group-by-select"), "topology.kubernetes.io/zone");

    const headers = screen.getAllByTestId("group-header");
    expect(headers.length).toBeGreaterThanOrEqual(1);
    // Mock data has us-west-2a (2 nodes) and us-west-2b (1 node)
    expect(headers[0]).toHaveTextContent("us-west-2a");
    expect(headers[0]).toHaveTextContent("2 nodes");
  });

  it("group-by with 'No grouping' removes group headers", async () => {
    mockFetchNodes.mockResolvedValue(MOCK_NODES);
    mockFetchLabels.mockResolvedValue(MOCK_LABELS);
    const user = userEvent.setup();
    render(<ClusterDashboard />);

    await waitFor(() => screen.getAllByTestId("node-row"));

    await user.selectOptions(screen.getByTestId("group-by-select"), "topology.kubernetes.io/zone");
    expect(screen.getAllByTestId("group-header").length).toBeGreaterThan(0);

    await user.selectOptions(screen.getByTestId("group-by-select"), "");
    expect(screen.queryByTestId("group-header")).not.toBeInTheDocument();
  });
});
