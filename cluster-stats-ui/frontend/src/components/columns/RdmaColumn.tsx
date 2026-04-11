import { NoDataSquare } from "../primitives/NoDataSquare";

export function RdmaColumn({ rdma }: { rdma: null }) {
  if (rdma === null) {
    return (
      <td data-testid="rdma-column">
        <NoDataSquare />
      </td>
    );
  }
}
