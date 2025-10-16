import React, { useRef, useEffect, useState, forwardRef } from 'react';
import { cn } from '@/lib/utils';
import { AnimatedBeam } from './magicui/animated-beam';

const Circle = forwardRef(({ className, children, icon: Icon, color = 'blue', isActive, isCompleted, size = 'default' }, ref) => {
  const colorClasses = {
    emerald: {
      bg: 'bg-emerald-50 dark:bg-emerald-900/20',
      border: 'border-emerald-400',
      active: 'ring-emerald-400',
      icon: 'text-emerald-600 dark:text-emerald-400',
      shadow: 'shadow-emerald-200 dark:shadow-emerald-900'
    },
    blue: {
      bg: 'bg-blue-50 dark:bg-blue-900/20',
      border: 'border-blue-400',
      active: 'ring-blue-400',
      icon: 'text-blue-600 dark:text-blue-400',
      shadow: 'shadow-blue-200 dark:shadow-blue-900'
    },
    purple: {
      bg: 'bg-purple-50 dark:bg-purple-900/20',
      border: 'border-purple-400',
      active: 'ring-purple-400',
      icon: 'text-purple-600 dark:text-purple-400',
      shadow: 'shadow-purple-200 dark:shadow-purple-900'
    },
    cyan: {
      bg: 'bg-cyan-50 dark:bg-cyan-900/20',
      border: 'border-cyan-400',
      active: 'ring-cyan-400',
      icon: 'text-cyan-600 dark:text-cyan-400',
      shadow: 'shadow-cyan-200 dark:shadow-cyan-900'
    },
    green: {
      bg: 'bg-green-50 dark:bg-green-900/20',
      border: 'border-green-400',
      active: 'ring-green-400',
      icon: 'text-green-600 dark:text-green-400',
      shadow: 'shadow-green-200 dark:shadow-green-900'
    },
    orange: {
      bg: 'bg-orange-50 dark:bg-orange-900/20',
      border: 'border-orange-400',
      active: 'ring-orange-400',
      icon: 'text-orange-600 dark:text-orange-400',
      shadow: 'shadow-orange-200 dark:shadow-orange-900'
    },
    amber: {
      bg: 'bg-amber-50 dark:bg-amber-900/20',
      border: 'border-amber-400',
      active: 'ring-amber-400',
      icon: 'text-amber-600 dark:text-amber-400',
      shadow: 'shadow-amber-200 dark:shadow-amber-900'
    },
    violet: {
      bg: 'bg-violet-50 dark:bg-violet-900/20',
      border: 'border-violet-400',
      active: 'ring-violet-400',
      icon: 'text-violet-600 dark:text-violet-400',
      shadow: 'shadow-violet-200 dark:shadow-violet-900'
    },
  };

  const colorSet = colorClasses[color] || colorClasses.blue;
  const sizeClasses = size === 'small' ? 'h-8 w-8' : 'h-12 w-12';
  const iconSize = size === 'small' ? 'h-3 w-3' : 'h-5 w-5';

  return (
    <div
      ref={ref}
      className={cn(
        'z-10 flex items-center justify-center rounded-full border-2 shadow-lg backdrop-blur-sm',
        sizeClasses,
        colorSet.bg,
        colorSet.border,
        colorSet.shadow,
        isActive && [
          `ring-4 ${colorSet.active}`,
          'ring-opacity-40',
          'scale-110',
          'shadow-2xl'
        ],
        isCompleted && 'opacity-60 scale-95',
        'transition-all duration-500 ease-in-out',
        'hover:scale-105 cursor-pointer',
        className,
      )}
      style={{
        animation: isActive ? 'pulse-strong 1.2s cubic-bezier(0.68, -0.55, 0.265, 1.55) infinite' : 'none'
      }}
    >
      {Icon && <Icon className={cn(iconSize, colorSet.icon, 'transition-transform duration-300', isActive && 'scale-110')} />}
      {children}
    </div>
  );
});

Circle.displayName = 'Circle';

export function AnimatedWorkflowDiagram({ 
  nodes = [], 
  edges = [], 
  currentNode = null, 
  activeEdges = [],
  onInterrupt = null,
  hitlEnabled = false,
  executionId = null
}) {
  const containerRef = useRef(null);
  const nodeRefs = useRef({});
  // Stable refs to the absolute-positioned node containers
  const nodeContainerRefs = useRef({});
  // Track container size to trigger re-renders on resize (so positions/lines recompute deterministically)
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
  // Delay edge rendering to avoid (0,0) initial positions causing stray lines in the top-left
  const [layoutReady, setLayoutReady] = useState(false);
  const [edgeCoords, setEdgeCoords] = useState({});

  // Create refs for all nodes
  nodes.forEach(node => {
    if (!nodeRefs.current[node.id]) {
      nodeRefs.current[node.id] = React.createRef();
    }
    if (!nodeContainerRefs.current[node.id]) {
      nodeContainerRefs.current[node.id] = React.createRef();
    }
  });

  const isNodeActive = (nodeId) => currentNode === nodeId;
  const isNodeCompleted = (nodeId) => {
    // Check if any edge from this node is active (meaning this node was already processed)
    return activeEdges.some(edge => edge.from === nodeId) && currentNode !== nodeId;
  };

  const isEdgeActive = (from, to) => {
    return activeEdges.some(edge => edge.from === from && edge.to === to);
  };

  // Compute responsive positions if nodes provide layer/col instead of absolute position
  const computePositions = () => {
    const container = containerRef.current;
    if (!container) return {};
    const rect = container.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;
    const paddingX = 40; // left/right padding for layout
    const paddingY = 0; // top/bottom padding for layout (reduced to increase vertical spacing)

    // Group nodes by layer if layer is provided
    const layers = new Map();
    nodes.forEach((n) => {
      if (n.layer != null) {
        const layerIndex = Number(n.layer);
        if (!layers.has(layerIndex)) layers.set(layerIndex, []);
        layers.get(layerIndex).push(n);
      }
    });

    if (layers.size === 0) {
      // No layer info; fall back to existing absolute positions
      const pos = {};
      nodes.forEach((n) => {
        if (n.position) pos[n.id] = n.position;
      });
      return pos;
    }

    const sortedLayers = Array.from(layers.keys()).sort((a, b) => a - b);
    const layerCount = sortedLayers.length;
    // For left-to-right layout: spread layers along X axis, and nodes within a layer along Y axis
    const availableWidth = Math.max(1, width - paddingX * 2);
    const availableHeight = Math.max(1, height - paddingY * 2);
    const layerGap = layerCount > 1 ? availableWidth / (layerCount - 1) : availableWidth / 2;

    const positions = {};
    sortedLayers.forEach((layerIdx, li) => {
      const layerNodes = layers.get(layerIdx) || [];
      const rowCount = layerNodes.length;
      const x = paddingX + li * layerGap; // fixed x per layer

      layerNodes.forEach((node, indexInLayer) => {
        // If node.col provided, treat it as row index (1-based); else spread evenly
        const row = node.col != null ? Number(node.col) - 1 : indexInLayer;
        const totalRows = node.totalCols != null ? Number(node.totalCols) : rowCount;
        const y = paddingY + (availableHeight * (row + 1)) / (totalRows + 1);
        
        // Ensure x and y are within bounds
        const clampedX = Math.max(paddingX, Math.min(width - paddingX, x));
        const clampedY = Math.max(paddingY, Math.min(height - paddingY, y));
        
        positions[node.id] = { x: clampedX, y: clampedY };
      });
    });

    return positions;
  };

  const responsivePositions = computePositions();

  useEffect(() => {
    // Schedule edge rendering on the next animation frame so nodes have been laid out
    let raf = requestAnimationFrame(() => setLayoutReady(true));
    return () => cancelAnimationFrame(raf);
    // Re-run when the node/edge list changes
  }, [nodes, edges]);

  // Observe container size only to trigger re-render -> positions and line endpoints recompute from pure data
  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver(entries => {
      const entry = entries[0];
      const cr = entry.contentRect;
      setContainerSize(prev => (prev.width !== cr.width || prev.height !== cr.height) ? { width: cr.width, height: cr.height } : prev);
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  return (
    <div className="relative w-full h-full min-h-[320px] max-h-[360px] flex items-center justify-center overflow-hidden bg-transparent rounded-xl p-3" ref={containerRef}>
      <style>{`
        @keyframes pulse-strong {
          0%, 100% {
            opacity: 1;
            transform: scale(1) rotate(0deg);
            filter: brightness(1) drop-shadow(0 0 0 currentColor);
          }
          25% {
            opacity: 0.9;
            transform: scale(1.1) rotate(-2deg);
            filter: brightness(1.15) drop-shadow(0 0 6px currentColor);
          }
          50% {
            opacity: 0.8;
            transform: scale(1.2) rotate(0deg);
            filter: brightness(1.3) drop-shadow(0 0 12px currentColor);
          }
          75% {
            opacity: 0.9;
            transform: scale(1.1) rotate(2deg);
            filter: brightness(1.15) drop-shadow(0 0 6px currentColor);
          }
        }
      `}</style>
      {/* Nodes */}
      {nodes.map((node) => {
        const Icon = node.icon;
        const pos = node.position || responsivePositions[node.id] || { x: 0, y: 0 };
        return (
          <div
            key={node.id}
            style={{
              position: 'absolute',
              left: `${pos.x}px`,
              top: `${pos.y}px`,
              transform: 'translate(-50%, -50%)',
            }}
            className="flex flex-col items-center gap-1.5 transition-all duration-300"
            ref={nodeContainerRefs.current[node.id]}
          >
            <Circle
              ref={nodeRefs.current[node.id]}
              icon={Icon}
              color={node.color}
              isActive={isNodeActive(node.id)}
              isCompleted={isNodeCompleted(node.id)}
              size={node.type === 'start' || node.type === 'end' ? 'small' : 'default'}
              data-node-id={node.id}
            />
            
            {/* HITL Control Buttons */}
            {hitlEnabled && isNodeActive(node.id) && node.hitlEnabled !== false && (
              <div className="flex gap-1 mt-2">
                <button
                  onClick={() => onInterrupt && onInterrupt(node.id, executionId)}
                  className="px-2 py-1 text-[8px] bg-red-500 hover:bg-red-600 text-white rounded transition-colors duration-200 shadow-sm"
                  title="Interrupt execution"
                >
                  ⏹️
                </button>
              </div>
            )}
            
            <div className="text-center max-w-[80px] transition-all duration-300">
              <div className={cn(
                'text-[10px] font-semibold transition-colors duration-300 leading-tight',
                isNodeActive(node.id) && 'text-blue-600 dark:text-blue-300',
                isNodeCompleted(node.id) && 'text-gray-400 dark:text-gray-600',
                !isNodeActive(node.id) && !isNodeCompleted(node.id) && 'text-gray-700 dark:text-gray-300'
              )}>
                {node.name}
              </div>
            </div>
          </div>
        );
      })}

      {/* Static SVG straight lines computed from layout positions (no DOM measurements) */}
      {layoutReady && (
        <svg className="absolute inset-0 w-full h-full z-0 pointer-events-none">
          <defs>
            <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L0,8 L8,4 z" fill="#94a3b8" />
            </marker>
          </defs>
          {edges.map((edge, index) => {
            const key = `${edge.from}-${edge.to}-${index}`;
            const fromPos = (nodes.find(n => n.id === edge.from)?.position) || responsivePositions[edge.from];
            const toPos = (nodes.find(n => n.id === edge.to)?.position) || responsivePositions[edge.to];
            if (!fromPos || !toPos) return null;

            const colorMap = {
              emerald: '#10b981',
              blue: '#3b82f6',
              purple: '#8b5cf6',
              cyan: '#06b6d4',
              green: '#22c55e',
              orange: '#f59e0b',
              amber: '#f59e0b',
              violet: '#8b5cf6',
            };
            const stroke = colorMap[edge.color] || '#64748b';
            const isActive = isEdgeActive(edge.from, edge.to);

            // Calculate offsets so the line touches the circle edges, not centers
            const fromNode = nodes.find(n => n.id === edge.from);
            const toNode = nodes.find(n => n.id === edge.to);
            const defaultRadius = 24; // h-12 => 48px diameter
            const smallRadius = 16;   // h-8  => 32px diameter
            const fromRadius = (fromNode?.type === 'start' || fromNode?.type === 'end') ? smallRadius : defaultRadius;
            const toRadius = (toNode?.type === 'start' || toNode?.type === 'end') ? smallRadius : defaultRadius;
            const dx = toPos.x - fromPos.x;
            const dy = toPos.y - fromPos.y;
            const dist = Math.hypot(dx, dy) || 1;
            const ux = dx / dist;
            const uy = dy / dist;
            const startX = fromPos.x + ux * fromRadius;
            const startY = fromPos.y + uy * fromRadius;
            const endX = toPos.x - ux * toRadius;
            const endY = toPos.y - uy * toRadius;
            const lineYOffset = -10; // raise lines slightly to align visually with circle centers

            return (
              <line
                key={key}
                x1={startX}
                y1={startY + lineYOffset}
                x2={endX}
                y2={endY + lineYOffset}
                stroke={stroke}
                strokeWidth={isActive ? 4 : 2}
                strokeOpacity={isActive ? 0.6 : 0.25}
                markerEnd="url(#arrow)"
              />
            );
          })}
        </svg>
      )}

      {/* Legend removed per requirement */}
    </div>
  );
}
