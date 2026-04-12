import { NoDataSquare } from "../primitives/NoDataSquare";

export function PcieColumn({ pcie }: { pcie: null }) {
  if (pcie === null) {
    return (
      <td data-testid="pcie-column">
        <NoDataSquare />
      </td>
    );
  }
}
