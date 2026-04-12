import { NoDataSquare } from "../primitives/NoDataSquare";

export function GpuColumn({ gpus }: { gpus: null }) {
  if (gpus === null) {
    return (
      <td data-testid="gpu-column">
        <NoDataSquare />
      </td>
    );
  }
}
