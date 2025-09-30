import React, { useRef, useEffect, forwardRef } from 'react';
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
  const sizeClasses = size === 'small' ? 'h-10 w-10' : 'h-14 w-14';
  const iconSize = size === 'small' ? 'h-4 w-4' : 'h-6 w-6';

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

export function AnimatedWorkflowDiagram({ nodes = [], edges = [], currentNode = null, activeEdges = [] }) {
  const containerRef = useRef(null);
  const nodeRefs = useRef({});

  // Create refs for all nodes
  nodes.forEach(node => {
    if (!nodeRefs.current[node.id]) {
      nodeRefs.current[node.id] = React.createRef();
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
    const paddingX = 48; // left/right padding for layout
    const paddingY = 24; // top/bottom padding for layout

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
    const availableHeight = Math.max(1, height - paddingY * 2);
    const layerGap = availableHeight / Math.max(1, layerCount - 1);

    const positions = {};
    sortedLayers.forEach((layerIdx, li) => {
      const layerNodes = layers.get(layerIdx) || [];
      const colCount = layerNodes.length;
      const y = paddingY + li * layerGap;

      layerNodes.forEach((node, indexInLayer) => {
        // If node.col provided, use it (1-based), else spread evenly
        const col = node.col != null ? Number(node.col) - 1 : indexInLayer;
        const totalCols = node.totalCols != null ? Number(node.totalCols) : colCount;
        const availableWidth = Math.max(1, width - paddingX * 2);
        const x = paddingX + (availableWidth * (col + 1)) / (totalCols + 1);
        positions[node.id] = { x, y };
      });
    });

    return positions;
  };

  const responsivePositions = computePositions();

  return (
    <div className="relative w-full h-[400px] flex items-center justify-center overflow-hidden bg-gradient-to-br from-slate-50 via-blue-50 to-purple-50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 rounded-xl p-4 shadow-inner" ref={containerRef}>
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
          >
            <Circle
              ref={nodeRefs.current[node.id]}
              icon={Icon}
              color={node.color}
              isActive={isNodeActive(node.id)}
              isCompleted={isNodeCompleted(node.id)}
              size={node.type === 'start' || node.type === 'end' ? 'small' : 'default'}
            />
            <div className="text-center max-w-[100px] transition-all duration-300">
              <div className={cn(
                'text-xs font-bold transition-colors duration-300',
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

      {/* Animated Beams */}
      {edges.map((edge, index) => {
        const fromRef = nodeRefs.current[edge.from];
        const toRef = nodeRefs.current[edge.to];
        
        if (!fromRef || !toRef) return null;

        const colorMap = {
          emerald: '#10b981',
          blue: '#3b82f6',
          purple: '#8b5cf6',
          cyan: '#06b6d4',
          green: '#10b981',
          orange: '#f59e0b',
          amber: '#f59e0b',
          violet: '#8b5cf6',
        };

        const pathColor = colorMap[edge.color] || '#3b82f6';
        const isActive = isEdgeActive(edge.from, edge.to);

        return (
          <AnimatedBeam
            key={`${edge.from}-${edge.to}-${index}`}
            containerRef={containerRef}
            fromRef={fromRef}
            toRef={toRef}
            pathColor={pathColor}
            pathWidth={isActive ? 5 : 2}
            pathOpacity={isActive ? 0.5 : 0.2}
            duration={isActive ? 1.5 : 5}
            curvature={20}
            startXOffset={0}
            startYOffset={0}
            endXOffset={0}
            endYOffset={0}
            gradientStartColor={pathColor}
            gradientStopColor={pathColor}
            reverse={false}
          />
        );
      })}

      {/* Legend */}
      <div className="absolute bottom-4 left-4 bg-white/95 dark:bg-slate-800/95 backdrop-blur-md rounded-lg p-3 shadow-xl border border-gray-200 dark:border-gray-700">
        <div className="text-[10px] font-bold mb-2 text-gray-800 dark:text-gray-200 uppercase tracking-wide">Status</div>
        <div className="flex flex-col gap-1.5 text-[10px]">
          <div className="flex items-center gap-2">
            <div className="h-2.5 w-2.5 rounded-full bg-blue-500 ring-2 ring-blue-400 ring-opacity-50 shadow-lg" style={{ animation: 'pulse-strong 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite' }}></div>
            <span className="text-gray-700 dark:text-gray-300 font-medium">Active</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-2.5 w-2.5 rounded-full bg-green-500 shadow-md"></div>
            <span className="text-gray-700 dark:text-gray-300 font-medium">Completed</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-2.5 w-2.5 rounded-full bg-gray-300 dark:bg-gray-600"></div>
            <span className="text-gray-700 dark:text-gray-300 font-medium">Pending</span>
          </div>
        </div>
      </div>
    </div>
  );
}
