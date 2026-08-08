import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import { memo } from "react";
import type { StepNodeData } from "./mapSpec";

export type StepFlowNode = Node<StepNodeData, "step">;

/** Compact step card for the canvas. */
function StepNodeInner({ id, data, selected }: NodeProps<StepFlowNode>) {
  return (
    <div
      className={`step-node ${selected ? "step-node--selected" : ""} ${
        data.isEntry ? "step-node--entry" : ""
      }`}
    >
      <Handle type="target" position={Position.Top} className="step-handle" />
      {data.isEntry && <span className="step-node__badge">entry</span>}
      <div className="step-node__title">{id}</div>
      <div className="step-node__type">{data.step_type}</div>
      <Handle type="source" position={Position.Bottom} className="step-handle" />
    </div>
  );
}

export default memo(StepNodeInner);
