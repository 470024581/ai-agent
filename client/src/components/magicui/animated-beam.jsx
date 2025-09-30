import { useEffect, useId, useRef, useState } from "react";
import { cn } from "@/lib/utils";

export const AnimatedBeam = ({
  className,
  containerRef,
  fromRef,
  toRef,
  curvature = 0,
  reverse = false,
  pathColor = "gray",
  pathWidth = 2,
  pathOpacity = 0.2,
  gradientStartColor = "#ffaa40",
  gradientStopColor = "#9c40ff",
  delay = 0,
  duration = 3,
  startXOffset = 0,
  startYOffset = 0,
  endXOffset = 0,
  endYOffset = 0,
}) => {
  const id = useId();
  const [pathD, setPathD] = useState("");
  const [svgDimensions, setSvgDimensions] = useState({ width: 0, height: 0 });
  
  const gradientCoordinates = reverse
    ? {
        x1: ["90%", "-10%"],
        x2: ["100%", "0%"],
        y1: ["0%", "0%"],
        y2: ["0%", "0%"],
      }
    : {
        x1: ["10%", "110%"],
        x2: ["0%", "100%"],
        y1: ["0%", "0%"],
        y2: ["0%", "0%"],
      };

  useEffect(() => {
    const updatePath = () => {
      if (containerRef.current && fromRef.current && toRef.current) {
        const containerRect = containerRef.current.getBoundingClientRect();
        const rectA = fromRef.current.getBoundingClientRect();
        const rectB = toRef.current.getBoundingClientRect();

        const svgWidth = containerRect.width;
        const svgHeight = containerRect.height;
        setSvgDimensions({ width: svgWidth, height: svgHeight });

        const startX =
          rectA.left - containerRect.left + rectA.width / 2 + startXOffset;
        const startY =
          rectA.top - containerRect.top + rectA.height / 2 + startYOffset;
        const endX =
          rectB.left - containerRect.left + rectB.width / 2 + endXOffset;
        const endY =
          rectB.top - containerRect.top + rectB.height / 2 + endYOffset;

        const controlY = startY - curvature;
        const d = `M ${startX},${startY} Q ${
          (startX + endX) / 2
        },${controlY} ${endX},${endY}`;
        setPathD(d);
      }
    };

    // Initialize ResizeObserver
    const resizeObserver = new ResizeObserver((entries) => {
      // We wrap it in requestAnimationFrame to avoid this error - ResizeObserver loop limit exceeded
      requestAnimationFrame(() => {
        if (!Array.isArray(entries) || !entries.length) {
          return;
        }
        updatePath();
      });
    });

    // Update initially
    updatePath();

    // Observe container for changes
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => {
      resizeObserver.disconnect();
    };
  }, [
    containerRef,
    fromRef,
    toRef,
    curvature,
    startXOffset,
    startYOffset,
    endXOffset,
    endYOffset,
  ]);

  return (
    <svg
      fill="none"
      width={svgDimensions.width}
      height={svgDimensions.height}
      xmlns="http://www.w3.org/2000/svg"
      className={cn(
        "pointer-events-none absolute left-0 top-0 transform-gpu stroke-2",
        className,
      )}
      viewBox={`0 0 ${svgDimensions.width} ${svgDimensions.height}`}
    >
      <path
        d={pathD}
        stroke={pathColor}
        strokeWidth={pathWidth}
        strokeOpacity={pathOpacity}
        strokeLinecap="round"
        strokeLinejoin="round"
        className="transition-all duration-700 ease-in-out"
      />
      <path
        d={pathD}
        strokeWidth={pathWidth}
        stroke={`url(#${id})`}
        strokeOpacity="1"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="transition-all duration-700 ease-in-out"
        filter="url(#glow)"
      />
      <defs>
        {/* Enhanced glow filter for more visible beam effect */}
        <filter id="glow" x="-100%" y="-100%" width="300%" height="300%">
          <feGaussianBlur stdDeviation="5" result="coloredBlur"/>
          <feColorMatrix in="coloredBlur" type="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 2 0"/>
          <feMerge>
            <feMergeNode in="coloredBlur"/>
            <feMergeNode in="coloredBlur"/>
            <feMergeNode in="SourceGraphic"/>
          </feMerge>
        </filter>
        
        {/* Gradient for animated beam */}
        <linearGradient
          className="transform-gpu"
          id={id}
          gradientUnits={"userSpaceOnUse"}
          x1={gradientCoordinates.x1[0]}
          x2={gradientCoordinates.x2[0]}
          y1={gradientCoordinates.y1[0]}
          y2={gradientCoordinates.y2[0]}
        >
          <stop stopColor={gradientStartColor} stopOpacity="0"></stop>
          <stop offset="15%" stopColor={gradientStartColor} stopOpacity="0.3"></stop>
          <stop offset="40%" stopColor={gradientStopColor} stopOpacity="0.9"></stop>
          <stop offset="50%" stopColor={gradientStopColor} stopOpacity="1"></stop>
          <stop offset="60%" stopColor={gradientStopColor} stopOpacity="0.9"></stop>
          <stop offset="85%" stopColor={gradientStopColor} stopOpacity="0.3"></stop>
          <stop offset="100%" stopColor={gradientStopColor} stopOpacity="0"></stop>
          <animateTransform
            attributeName="gradientTransform"
            type="translate"
            from={gradientCoordinates.x1[1] + " 0"}
            to={gradientCoordinates.x1[0] + " 0"}
            dur={`${duration}s`}
            begin={`${delay}s`}
            repeatCount="indefinite"
            calcMode="spline"
            keySplines="0.42 0 0.58 1"
          />
        </linearGradient>
      </defs>
    </svg>
  );
};
