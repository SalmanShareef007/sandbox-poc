"use client";

import { useId, useState } from "react";

const W = 600;
const H = 200;
const PAD = { top: 16, right: 12, bottom: 24, left: 12 };

const money = (n: number) =>
  n.toLocaleString("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });

interface SpendChartProps {
  /** Cumulative spend in INR, one value per week. */
  values: number[];
  budget?: number;
}

export default function SpendChart({ values, budget }: SpendChartProps) {
  const [hover, setHover] = useState<number | null>(null);
  // Strip characters React ids may contain that break `url(#...)` references.
  const fillId = `spend-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  if (values.length === 0) return null;

  const max = Math.max(...values, budget ?? 0) || 1;
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;
  const baseline = PAD.top + innerH;
  const step = values.length > 1 ? innerW / (values.length - 1) : 0;

  const points = values.map((v, i) => ({
    x: PAD.left + i * step,
    y: PAD.top + innerH - (v / max) * innerH,
    v,
    week: i + 1,
  }));

  const line = points.map((p, i) => `${i ? "L" : "M"}${p.x},${p.y}`).join(" ");
  const area = `${line} L${points[points.length - 1].x},${baseline} L${points[0].x},${baseline} Z`;
  const budgetY = budget ? PAD.top + innerH - (budget / max) * innerH : null;
  const active = hover !== null ? points[hover] : null;

  return (
    <div>
      <div className="relative h-48">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-full w-full"
        preserveAspectRatio="none"
        role="img"
        aria-label={`Weekly cumulative spend over ${values.length} weeks, from ${money(values[0])} to ${money(values[values.length - 1])}`}
        onMouseLeave={() => setHover(null)}
      >
        <defs>
          <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.35" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </linearGradient>
        </defs>

        {budgetY !== null && (
          <line
            x1={PAD.left}
            x2={W - PAD.right}
            y1={budgetY}
            y2={budgetY}
            stroke="var(--muted)"
            strokeDasharray="4 4"
            strokeWidth={1}
            vectorEffect="non-scaling-stroke"
          />
        )}

        <line
          x1={PAD.left}
          x2={W - PAD.right}
          y1={baseline}
          y2={baseline}
          stroke="var(--border)"
          strokeWidth={1}
          vectorEffect="non-scaling-stroke"
        />

        <path d={area} fill={`url(#${fillId})`} />
        <path
          d={line}
          fill="none"
          stroke="var(--accent)"
          strokeWidth={2}
          vectorEffect="non-scaling-stroke"
        />

        {active && (
          <line
            x1={active.x}
            x2={active.x}
            y1={PAD.top}
            y2={baseline}
            stroke="var(--muted)"
            strokeWidth={1}
            vectorEffect="non-scaling-stroke"
          />
        )}

        {points.map((p, i) => (
          <rect
            key={i}
            x={p.x - step / 2}
            y={0}
            width={step || innerW}
            height={H}
            fill="transparent"
            onMouseEnter={() => setHover(i)}
          />
        ))}
      </svg>

      {active && (
        <>
          <span
            className="pointer-events-none absolute h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 border-2 border-surface bg-accent"
            style={{ left: `${(active.x / W) * 100}%`, top: `${(active.y / H) * 100}%` }}
          />
          <div
            className="pointer-events-none absolute -translate-x-1/2 -translate-y-full border border-border bg-surface px-2.5 py-1.5 text-xs shadow-card"
            style={{
              left: `${Math.min(Math.max((active.x / W) * 100, 10), 90)}%`,
              top: `calc(${(active.y / H) * 100}% - 10px)`,
            }}
          >
            <p className="text-muted">Week {active.week}</p>
            <p className="font-semibold text-foreground">{money(active.v)}</p>
          </div>
        </>
      )}
      </div>

      <div className="mt-2 flex justify-between text-xs text-muted">
        <span>Week 1</span>
        {budget ? <span>Dashed line: {money(budget)} budget</span> : null}
        <span>Week {values.length}</span>
      </div>
    </div>
  );
}
