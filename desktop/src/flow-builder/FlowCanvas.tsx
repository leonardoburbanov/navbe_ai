import {
  Background,
  Controls,
  ReactFlow,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
  type OnSelectionChangeParams,
  type ReactFlowInstance,
} from "@xyflow/react";
import { useCallback, useMemo, useRef, type DragEvent } from "react";
import "@xyflow/react/dist/style.css";
import { STEP_DRAG_MIME } from "./Palette";
import { STEP_NODE_TYPE, type FlowEdgeData, type StepNodeData } from "./mapSpec";
import StepNode from "./StepNode";

interface FlowCanvasProps {
  nodes: Node<StepNodeData>[];
  edges: Edge<FlowEdgeData>[];
  onNodesChange: (changes: NodeChange<Node<StepNodeData>>[]) => void;
  onEdgesChange: (changes: EdgeChange<Edge<FlowEdgeData>>[]) => void;
  onConnect: (connection: Connection) => void;
  onSelectionChange: (params: OnSelectionChangeParams) => void;
  onDropStep: (stepType: string, position: { x: number; y: number }) => void;
  onNodeDragStop: () => void;
}

/** React Flow canvas with drop target for palette steps. */
export default function FlowCanvas({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onConnect,
  onSelectionChange,
  onDropStep,
  onNodeDragStop,
}: FlowCanvasProps) {
  const nodeTypes = useMemo(() => ({ [STEP_NODE_TYPE]: StepNode }), []);
  const rfRef = useRef<ReactFlowInstance<Node<StepNodeData>, Edge<FlowEdgeData>> | null>(null);

  const onDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      const stepType = e.dataTransfer.getData(STEP_DRAG_MIME);
      if (!stepType || !rfRef.current) return;
      const position = rfRef.current.screenToFlowPosition({
        x: e.clientX,
        y: e.clientY,
      });
      onDropStep(stepType, position);
    },
    [onDropStep],
  );

  return (
    <div className="flow-canvas">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onSelectionChange={onSelectionChange}
        onInit={(instance) => {
          rfRef.current = instance;
        }}
        onDragOver={onDragOver}
        onDrop={onDrop}
        onNodeDragStop={onNodeDragStop}
        fitView
        colorMode="dark"
        deleteKeyCode={["Backspace", "Delete"]}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={16} size={1} />
        <Controls />
      </ReactFlow>
    </div>
  );
}
