import { useRef, useState, useCallback } from "react";

interface PolygonEditorProps {
  polygon: number[][];
  onChange: (polygon: number[][]) => void;
  resolution: [number, number];
}

const VERTEX_RADIUS = 0.015;

function round4(v: number): number {
  return Math.round(v * 10000) / 10000;
}

function clamp(v: number): number {
  return Math.min(1, Math.max(0, v));
}

export default function PolygonEditor({ polygon, onChange, resolution }: PolygonEditorProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [draggingIndex, setDraggingIndex] = useState<number | null>(null);

  const toNormalized = useCallback(
    (e: React.PointerEvent): [number, number] => {
      const rect = svgRef.current!.getBoundingClientRect();
      const x = clamp((e.clientX - rect.left) / rect.width);
      const y = clamp((e.clientY - rect.top) / rect.height);
      return [round4(x), round4(y)];
    },
    [],
  );

  const handleBackgroundPointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (e.button !== 0) return;
      const [x, y] = toNormalized(e);
      onChange([...polygon, [x, y]]);
    },
    [polygon, onChange, toNormalized],
  );

  const handleVertexPointerDown = useCallback(
    (e: React.PointerEvent, index: number) => {
      if (e.button !== 0) return;
      e.stopPropagation();
      setDraggingIndex(index);
      (e.target as Element).setPointerCapture(e.pointerId);
    },
    [],
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (draggingIndex === null) return;
      const [x, y] = toNormalized(e);
      const updated = polygon.map((pt, i) => (i === draggingIndex ? [x, y] : pt));
      onChange(updated);
    },
    [draggingIndex, polygon, onChange, toNormalized],
  );

  const handlePointerUp = useCallback(() => {
    setDraggingIndex(null);
  }, []);

  const handleVertexContextMenu = useCallback(
    (e: React.MouseEvent, index: number) => {
      e.preventDefault();
      e.stopPropagation();
      onChange(polygon.filter((_, i) => i !== index));
    },
    [polygon, onChange],
  );

  const points = polygon.map((pt) => `${pt[0]},${pt[1]}`).join(" ");
  const [w, h] = resolution;

  return (
    <div className="max-w-lg" style={{ aspectRatio: `${w}/${h}` }}>
      <svg
        ref={svgRef}
        viewBox="0 0 1 1"
        preserveAspectRatio="none"
        className="w-full h-full rounded-md border border-gray-300"
        style={{ touchAction: "none", userSelect: "none" }}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
      >
        {/* Background */}
        <rect
          x="0"
          y="0"
          width="1"
          height="1"
          fill="#374151"
          cursor="crosshair"
          onPointerDown={handleBackgroundPointerDown}
        />

        {/* Polygon fill + stroke */}
        {polygon.length >= 3 && (
          <polygon
            points={points}
            fill="rgba(59,130,246,0.2)"
            stroke="#3b82f6"
            strokeWidth={0.004}
            pointerEvents="none"
          />
        )}

        {/* Line for 2-point case */}
        {polygon.length === 2 && (
          <line
            x1={polygon[0][0]}
            y1={polygon[0][1]}
            x2={polygon[1][0]}
            y2={polygon[1][1]}
            stroke="#3b82f6"
            strokeWidth={0.004}
            pointerEvents="none"
          />
        )}

        {/* Vertex handles */}
        {polygon.map((pt, i) => (
          <circle
            key={i}
            cx={pt[0]}
            cy={pt[1]}
            r={VERTEX_RADIUS}
            fill="white"
            stroke="#3b82f6"
            strokeWidth={0.003}
            cursor={draggingIndex === i ? "grabbing" : "grab"}
            onPointerDown={(e) => handleVertexPointerDown(e, i)}
            onContextMenu={(e) => handleVertexContextMenu(e, i)}
          />
        ))}
      </svg>
    </div>
  );
}
