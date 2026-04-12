import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { FilterBar } from "../components/FilterBar";
import { MOCK_LABELS } from "../api/mock-data";

describe("FilterBar", () => {
  it("renders suggestions from label data", async () => {
    const user = userEvent.setup();
    render(
      <FilterBar labelsData={MOCK_LABELS} activeFilters={[]} onAddFilter={() => {}} onRemoveFilter={() => {}} groupBy={null} onGroupByChange={() => {}} />,
    );
    await user.click(screen.getByTestId("filter-input"));
    expect(screen.getByTestId("filter-dropdown")).toBeInTheDocument();
  });

  it("filters suggestions as user types", async () => {
    const user = userEvent.setup();
    render(
      <FilterBar labelsData={MOCK_LABELS} activeFilters={[]} onAddFilter={() => {}} onRemoveFilter={() => {}} groupBy={null} onGroupByChange={() => {}} />,
    );
    await user.type(screen.getByTestId("filter-input"), "zone");
    const dropdown = screen.getByTestId("filter-dropdown");
    expect(dropdown.textContent).toContain("zone");
  });

  it("calls onAddFilter when suggestion is selected", async () => {
    const onAdd = vi.fn();
    const user = userEvent.setup();
    render(
      <FilterBar labelsData={MOCK_LABELS} activeFilters={[]} onAddFilter={onAdd} onRemoveFilter={() => {}} groupBy={null} onGroupByChange={() => {}} />,
    );
    await user.click(screen.getByTestId("filter-input"));
    const dropdown = screen.getByTestId("filter-dropdown");
    const firstItem = dropdown.querySelector(".ac-item") as HTMLElement;
    await user.click(firstItem);
    expect(onAdd).toHaveBeenCalled();
  });

  it("renders active filter chips", () => {
    render(
      <FilterBar
        labelsData={MOCK_LABELS}
        activeFilters={["topology.kubernetes.io/zone=us-west-2a"]}
        onAddFilter={() => {}} onRemoveFilter={() => {}} groupBy={null} onGroupByChange={() => {}}
      />,
    );
    expect(screen.getByTestId("filter-chips")).toHaveTextContent("topology.kubernetes.io/zone=us-west-2a");
  });

  it("calls onRemoveFilter when chip X is clicked", async () => {
    const onRemove = vi.fn();
    const user = userEvent.setup();
    render(
      <FilterBar
        labelsData={MOCK_LABELS}
        activeFilters={["topology.kubernetes.io/zone=us-west-2a"]}
        onAddFilter={() => {}} onRemoveFilter={onRemove} groupBy={null} onGroupByChange={() => {}}
      />,
    );
    await user.click(screen.getByTestId("remove-filter"));
    expect(onRemove).toHaveBeenCalledWith(0);
  });

  it("group-by select shows label keys", () => {
    render(
      <FilterBar labelsData={MOCK_LABELS} activeFilters={[]} onAddFilter={() => {}} onRemoveFilter={() => {}} groupBy={null} onGroupByChange={() => {}} />,
    );
    const select = screen.getByTestId("group-by-select") as HTMLSelectElement;
    const options = [...select.options].map((o) => o.value);
    expect(options).toContain("");
    expect(options).toContain("topology.kubernetes.io/zone");
  });

  it("calls onGroupByChange when a label key is selected", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(
      <FilterBar labelsData={MOCK_LABELS} activeFilters={[]} onAddFilter={() => {}} onRemoveFilter={() => {}} groupBy={null} onGroupByChange={onChange} />,
    );
    await user.selectOptions(screen.getByTestId("group-by-select"), "topology.kubernetes.io/zone");
    expect(onChange).toHaveBeenCalledWith("topology.kubernetes.io/zone");
  });

  it("calls onGroupByChange with null when 'No grouping' is selected", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(
      <FilterBar labelsData={MOCK_LABELS} activeFilters={[]} onAddFilter={() => {}} onRemoveFilter={() => {}} groupBy="topology.kubernetes.io/zone" onGroupByChange={onChange} />,
    );
    await user.selectOptions(screen.getByTestId("group-by-select"), "");
    expect(onChange).toHaveBeenCalledWith(null);
  });
});
