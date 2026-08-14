/**
 * The chart primitives, drawn as plain SVG.
 *
 * No charting library: three forms cover everything this app measures, and each is fifty
 * lines. What matters more than the code is the discipline they encode --
 *
 *   one hue          every mark is the brand blue at one of two lightnesses. Nothing here
 *                    is a categorical series, so no colour is asked to carry identity: the
 *                    axis label does that, and colour is free to mean "this is the data".
 *   thin marks       2px lines, 4px rounded bar ends anchored to the baseline, 10px
 *                    markers, and a grid recessive enough to read past.
 *   a hover layer    an SVG chart on a screen is interactive whether or not you plan for
 *                    it. Every form here ships a tooltip; none labels every point.
 *
 * Widths come from a ResizeObserver rather than a viewBox stretch, so type stays 11px at
 * every container size instead of scaling with the box.
 */

import { useEffect, useRef, useState } from "react";

const INK = {
  mark: "var(--color-primary)",
  markSoft: "var(--color-primary-light)",
  grid: "var(--color-border-light)",
  axis: "var(--color-subtle)",
  label: "var(--color-muted)",
  surface: "var(--color-surface)",
};

/** Container width in CSS pixels, so the chart draws at 1:1 and text never scales. */
function useWidth() {
  const ref = useRef(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const element = ref.current;
    if (!element) return undefined;
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(element);
    // Measuring a DOM node is a read from an external system, which is what an effect is
    // for; the observer covers every later resize.
    setWidth(element.clientWidth);
    return () => observer.disconnect();
  }, []);

  return [ref, width];
}

/** A round upper bound with a readable step, so the axis reads 0/25/50/75/100 not 0/37/74. */
function niceScale(max, ticks = 4) {
  if (!max || max <= 0) return { max: ticks, step: 1 };
  const raw = max / ticks;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= raw) || magnitude * 10;
  return { max: step * ticks, step };
}

/**
 * A tooltip chip: rounded rect plus centred text, kept inside the plot so it never clips
 * at the first or last point.
 */
function Chip({ x, y, text, width }) {
  const w = text.length * 6.4 + 18;
  const clamped = Math.max(w / 2 + 2, Math.min(width - w / 2 - 2, x));
  // A point at the very top of the scale would otherwise push its own label off the plot.
  const top = Math.max(26, y);
  return (
    <g pointerEvents="none">
      <rect
        x={clamped - w / 2}
        y={top - 26}
        width={w}
        height={22}
        rx={7}
        fill={INK.surface}
        stroke="var(--color-primary-light)"
        strokeWidth={1.5}
      />
      <text
        x={clamped}
        y={top - 11}
        textAnchor="middle"
        fontSize="11.5"
        fontWeight="700"
        fill="var(--color-primary)"
      >
        {text}
      </text>
    </g>
  );
}

function EmptyPlot({ height, message }) {
  return (
    <div
      className="flex items-center justify-center text-[13px] text-subtle border border-dashed border-border rounded-xl"
      style={{ height }}
    >
      {message}
    </div>
  );
}

/**
 * Change over time. One series, so no legend -- the card's title names it.
 *
 * The curve is smoothed with control points that share their endpoint's y, which keeps the
 * line from overshooting into values the data never took: a study-hours line that dips
 * below zero between two real points is a lie the eye believes.
 */
export function LineChart({
  data,
  height = 240,
  formatValue = (n) => String(n),
  emptyMessage = "No activity in this period yet.",
}) {
  const [ref, width] = useWidth();
  const [hover, setHover] = useState(null);

  const hasData = data.length > 0 && data.some((point) => point.value > 0);

  const pad = { top: 24, right: 12, bottom: 28, left: 34 };
  const plotW = Math.max(0, width - pad.left - pad.right);
  const plotH = height - pad.top - pad.bottom;

  const { max, step } = niceScale(Math.max(...data.map((d) => d.value), 0));
  const ticks = [];
  for (let value = 0; value <= max; value += step) ticks.push(value);

  const x = (index) => pad.left + (data.length === 1 ? plotW / 2 : (plotW * index) / (data.length - 1));
  const y = (value) => pad.top + plotH - (plotH * value) / max;

  let line = "";
  let area = "";
  if (width > 0 && data.length > 0) {
    const points = data.map((point, index) => [x(index), y(point.value)]);
    line = points.reduce((path, [px, py], index) => {
      if (index === 0) return `M ${px} ${py}`;
      const [prevX, prevY] = points[index - 1];
      const cx = (px - prevX) / 3;
      return `${path} C ${prevX + cx} ${prevY}, ${px - cx} ${py}, ${px} ${py}`;
    }, "");
    area = `${line} L ${points[points.length - 1][0]} ${pad.top + plotH} L ${points[0][0]} ${pad.top + plotH} Z`;
  }

  return (
    <div ref={ref}>
      {!hasData ? (
        <EmptyPlot height={height} message={emptyMessage} />
      ) : width > 0 ? (
        <svg width={width} height={height} role="img" aria-label="Activity over time">
          <defs>
            <linearGradient id="line-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--color-primary)" stopOpacity="0.16" />
              <stop offset="100%" stopColor="var(--color-primary)" stopOpacity="0" />
            </linearGradient>
          </defs>

          {ticks.map((tick) => (
            <g key={tick}>
              <line
                x1={pad.left}
                x2={pad.left + plotW}
                y1={y(tick)}
                y2={y(tick)}
                stroke={INK.grid}
                strokeWidth={1}
              />
              <text x={pad.left - 10} y={y(tick) + 4} textAnchor="end" fontSize="11" fill={INK.axis}>
                {tick}
              </text>
            </g>
          ))}

          <path d={area} fill="url(#line-fill)" />
          <path
            d={line}
            fill="none"
            stroke={INK.mark}
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {data.map((point, index) => (
            <text
              key={point.label}
              x={x(index)}
              y={height - 8}
              textAnchor="middle"
              fontSize="11"
              fill={INK.label}
            >
              {point.label}
            </text>
          ))}

          {hover !== null && (
            <g pointerEvents="none">
              <line
                x1={x(hover)}
                x2={x(hover)}
                y1={pad.top}
                y2={pad.top + plotH}
                stroke="var(--color-primary-light)"
                strokeWidth={1.5}
                strokeDasharray="4 4"
              />
              {/* A 2px surface ring keeps the marker legible where it lands on the line. */}
              <circle cx={x(hover)} cy={y(data[hover].value)} r={5.5} fill={INK.surface} stroke={INK.mark} strokeWidth={2.5} />
              <Chip
                x={x(hover)}
                y={y(data[hover].value)}
                width={width}
                text={`${data[hover].label} · ${formatValue(data[hover].value)}`}
              />
            </g>
          )}

          {/* Hit targets are the full column height, not the 11px marker. */}
          {data.map((point, index) => (
            <rect
              key={`hit-${point.label}`}
              x={x(index) - (plotW / Math.max(1, data.length - 1)) / 2}
              y={pad.top}
              width={plotW / Math.max(1, data.length - 1)}
              height={plotH}
              fill="transparent"
              onMouseEnter={() => setHover(index)}
              onMouseLeave={() => setHover(null)}
            />
          ))}
        </svg>
      ) : (
        <div style={{ height }} />
      )}
    </div>
  );
}

/**
 * Magnitude by category. A pale full-height track behind every bar gives the eye a common
 * ceiling to judge the short bars against, which a bare bar chart does not.
 */
export function BarChart({
  data,
  height = 200,
  formatValue = (n) => String(n),
  emptyMessage = "Nothing to chart yet.",
}) {
  const [ref, width] = useWidth();
  const [hover, setHover] = useState(null);

  const hasData = data.length > 0 && data.some((bar) => bar.value > 0);
  const pad = { top: 26, bottom: 26 };
  const plotH = height - pad.top - pad.bottom;
  const { max } = niceScale(Math.max(...data.map((d) => d.value), 0), 2);

  const slot = data.length ? width / data.length : 0;
  const barW = Math.max(6, Math.min(20, slot - 10));

  return (
    <div ref={ref}>
      {!hasData ? (
        <EmptyPlot height={height} message={emptyMessage} />
      ) : width > 0 ? (
        <svg width={width} height={height} role="img" aria-label="Totals by category">
          {data.map((bar, index) => {
            const cx = slot * index + slot / 2;
            const barH = Math.max(3, (plotH * bar.value) / max);
            const top = pad.top + plotH - barH;
            const active = hover === index;

            return (
              <g
                key={bar.label}
                onMouseEnter={() => setHover(index)}
                onMouseLeave={() => setHover(null)}
              >
                <rect x={cx - slot / 2} y={0} width={slot} height={height} fill="transparent" />
                <rect
                  x={cx - barW / 2}
                  y={pad.top}
                  width={barW}
                  height={plotH}
                  rx={barW / 2}
                  fill={INK.grid}
                />
                {/* Rounded at the data end, square where it meets the baseline. */}
                <path
                  d={`M ${cx - barW / 2} ${pad.top + plotH}
                      L ${cx - barW / 2} ${top + 4}
                      Q ${cx - barW / 2} ${top} ${cx - barW / 2 + 4} ${top}
                      L ${cx + barW / 2 - 4} ${top}
                      Q ${cx + barW / 2} ${top} ${cx + barW / 2} ${top + 4}
                      L ${cx + barW / 2} ${pad.top + plotH} Z`}
                  fill={active ? "var(--color-primary-dark)" : INK.mark}
                />
                <text x={cx} y={height - 8} textAnchor="middle" fontSize="11" fill={INK.label}>
                  {bar.label}
                </text>
                {active && <Chip x={cx} y={top} width={width} text={formatValue(bar.value)} />}
              </g>
            );
          })}
        </svg>
      ) : (
        <div style={{ height }} />
      )}
    </div>
  );
}

/**
 * One ratio, as a ring around the figure it describes. A single number does not need a
 * plot, but a pass rate is read against 100% -- and the ring is the cheapest way to show
 * the whole that the number is part of.
 */
export function ProgressRing({ value, size = 120, stroke = 10, label }) {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, value ?? 0));

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" role="img" aria-label={`${clamped}%`}>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={INK.grid} strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={INK.mark}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - clamped / 100)}
          style={{ transition: "stroke-dashoffset 0.6s ease" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-[22px] font-bold text-heading leading-none">{Math.round(clamped)}%</span>
        {label && <span className="text-[11px] text-muted mt-1">{label}</span>}
      </div>
    </div>
  );
}

/**
 * A labelled proportion bar: the row form of the same information as the ring, for the
 * cases where the label matters as much as the number.
 */
export function MeterRow({ label, value, total, hint }) {
  const percent = total ? Math.round((value / total) * 100) : 0;
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3 mb-1.5">
        <span className="text-[13px] font-medium text-heading">{label}</span>
        <span className="text-[12px] text-muted tabular-nums">
          {value}
          <span className="text-subtle"> / {total}</span>
          <span className="ml-2 font-semibold text-heading">{percent}%</span>
        </span>
      </div>
      <div className="track">
        <span style={{ width: `${percent}%` }} />
      </div>
      {hint && <p className="text-[11px] text-subtle mt-1">{hint}</p>}
    </div>
  );
}
