'use client';

import { useEffect, useState, useMemo } from 'react';
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceArea,
  ResponsiveContainer,
  Customized,
} from 'recharts';
import type { FearGreedHistoryPoint } from '@/app/api/fear-greed-history/route';

// ── Types ─────────────────────────────────────────────────────────────────────

interface ChartPoint {
  rawDate:   string;
  dateLabel: string;
  fgAll:     number | null;
  ihsg:      number | null;
  label:     string;
}

interface ApiResponse {
  points: FearGreedHistoryPoint[];
  days:   number;
}

// ── Constants ─────────────────────────────────────────────────────────────────

// ── Helpers ───────────────────────────────────────────────────────────────────

// Line color: contrarian (Fear=green=opportunity, Greed=red=caution)
// Must match the Line stroke colors exactly
function fgColor(score: number): string {
  if (score < 25)  return '#059669';  // Extreme Fear  — dark green
  if (score < 40)  return '#10B981';  // Fear          — green
  if (score < 60)  return '#F59E0B';  // Neutral       — yellow
  if (score < 75)  return '#EF4444';  // Greed         — red
  return '#DC2626';                    // Extreme Greed — dark red
}

// Stats text color: intuitive (Fear=red=bad, Greed=green=good)
function getFGTextColor(score: number): string {
  if (score <= 40) return '#EF4444';  // Fear zones — red text
  if (score <= 60) return '#F59E0B';  // Neutral    — yellow text
  return '#10B981';                    // Greed zones — green text
}

function formatDateLabel(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('id-ID', { day: 'numeric', month: 'short' });
}

function formatDateShort(dateStr: string | null): string {
  if (!dateStr) return '—';
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('id-ID', { day: 'numeric', month: 'short' });
}

// ── Custom Tooltip ────────────────────────────────────────────────────────────

interface TooltipPayloadItem {
  dataKey: string;
  value:   number | null;
  payload: ChartPoint;
}

interface CustomTooltipProps {
  active?:  boolean;
  payload?: TooltipPayloadItem[];
  label?:   string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  const pt = payload[0]?.payload as ChartPoint | undefined;
  if (!pt) return null;

  const fgVal   = pt.fgAll;
  const ihsgVal = pt.ihsg;
  const fgLabel = pt.label;

  return (
    <div className="bg-white border border-[#e5e2db] rounded-xl shadow-lg p-3 text-xs min-w-[150px]">
      <p className="font-semibold text-[#6b7280] mb-2 pb-1.5 border-b border-[#f0ede8]">{label}</p>
      {fgVal != null && (
        <div className="flex items-center justify-between gap-3 mb-1">
          <span className="text-[#9ca3af]">Fear &amp; Greed</span>
          <span className="font-bold tabular-nums" style={{ color: fgColor(fgVal) }}>
            {fgVal.toFixed(1)}
          </span>
        </div>
      )}
      {fgLabel && fgVal != null && (
        <div className="flex items-center justify-between gap-3 mb-1">
          <span className="text-[#9ca3af]">Status</span>
          <span className="font-semibold" style={{ color: fgColor(fgVal) }}>{fgLabel}</span>
        </div>
      )}
      {ihsgVal != null && (
        <div className="flex items-center justify-between gap-3 mt-1.5 pt-1.5 border-t border-[#f0ede8]">
          <span className="text-[#9ca3af]">IHSG</span>
          <span className="font-semibold text-[#374151] tabular-nums">
            {Math.round(ihsgVal).toLocaleString('id-ID')}
          </span>
        </div>
      )}
    </div>
  );
}

// ── Stat item ─────────────────────────────────────────────────────────────────

function StatItem({
  label, value, sub, color,
}: {
  label:  string;
  value:  string | number | null;
  sub?:   string;
  color?: string;
}) {
  return (
    <div className="flex items-baseline gap-2 px-4 first:pl-5 last:pr-5">
      <span className="text-[10px] font-semibold uppercase tracking-widest text-[#9ca3af] whitespace-nowrap">
        {label}
      </span>
      <span className="text-sm font-bold tabular-nums leading-none" style={{ color: color ?? '#0f172a' }}>
        {value ?? '—'}
      </span>
      {sub && <span className="text-[10px] text-[#9ca3af]">{sub}</span>}
    </div>
  );
}

// ── Colored F&G line overlay ──────────────────────────────────────────────────
// Draws colored SVG <line> segments using Recharts' injected scale functions.
// Customized component receives: xAxisMap, yAxisMap (with .scale()), data array.
// This is the reliable approach — no dependency on formattedGraphicalItems.

type ScaleFn = { (v: string): number; bandwidth?: () => number };
type AxisEntry = { scale: ScaleFn; orientation?: string };

function FGColoredLine(props: Record<string, unknown>) {
  const xAxisMap = props.xAxisMap as Record<string | number, AxisEntry> | undefined;
  const yAxisMap = props.yAxisMap as Record<string, AxisEntry>          | undefined;
  const data     = props.data     as ChartPoint[]                        | undefined;

  if (!xAxisMap || !yAxisMap || !data || data.length < 2) return null;

  const xAxis = Object.values(xAxisMap)[0];
  const yAxis = yAxisMap['fg'];          // matches <YAxis yAxisId="fg">
  if (!xAxis?.scale || !yAxis?.scale) return null;

  const bw = xAxis.scale.bandwidth?.() ?? 0;
  const segs: React.ReactElement[] = [];

  for (let i = 0; i < data.length - 1; i++) {
    const curr = data[i];
    const next = data[i + 1];
    if (curr.fgAll == null || next.fgAll == null) continue;

    /* eslint-disable @typescript-eslint/no-explicit-any */
    const x1 = (xAxis.scale as any)(curr.dateLabel) + bw / 2;
    const y1 = (yAxis.scale as any)(curr.fgAll);
    const x2 = (xAxis.scale as any)(next.dateLabel) + bw / 2;
    const y2 = (yAxis.scale as any)(next.fgAll);
    /* eslint-enable @typescript-eslint/no-explicit-any */

    if (isNaN(x1) || isNaN(y1) || isNaN(x2) || isNaN(y2)) continue;

    segs.push(
      <line
        key={i}
        x1={x1} y1={y1} x2={x2} y2={y2}
        stroke={fgColor(curr.fgAll)}
        strokeWidth={2.5}
        strokeLinecap="round"
      />
    );
  }

  return <g>{segs}</g>;
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function FearGreedChart() {
  const [allPoints, setAllPoints] = useState<FearGreedHistoryPoint[]>([]);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState<string | null>(null);
  const [isMobile,  setIsMobile]  = useState(false);

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 640);
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  useEffect(() => {
    fetch('/api/fear-greed-history?days=all')
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<ApiResponse>;
      })
      .then(d => { setAllPoints(d.points); setLoading(false); })
      .catch(() => { setError('Gagal memuat data historis'); setLoading(false); });
  }, []);

  const rangeStats = useMemo(() => {
    let high = -Infinity, highDate = '';
    let low  =  Infinity, lowDate  = '';
    for (const p of allPoints) {
      const v = p.fgSmoothed;
      if (v == null) continue;
      if (v > high) { high = v; highDate = p.date; }
      if (v < low)  { low  = v; lowDate  = p.date; }
    }
    return {
      high:     high === -Infinity ? null : high,
      highDate: highDate || null,
      low:      low  ===  Infinity ? null : low,
      lowDate:  lowDate  || null,
    };
  }, [allPoints]);

  // Build chart data — simple map, IHSG carry-forward for holidays only.
  // Zone coloring is handled entirely by ColoredFGLine overlay, not data keys.
  const chartData = useMemo<ChartPoint[]>(() => {
    let lastIhsg: number | null = null;
    return allPoints.map(p => {
      if (p.ihsgClose !== null) lastIhsg = p.ihsgClose;
      return {
        rawDate:   p.date,
        dateLabel: formatDateLabel(p.date),
        fgAll:     p.fgSmoothed,
        ihsg:      p.ihsgClose !== null ? p.ihsgClose : lastIhsg,
        label:     p.label,
      };
    });
  }, [allPoints]);

  const currentPoint = useMemo(() => {
    const live = allPoints.filter(p => !p.isBackfilled);
    if (live.length) return live[live.length - 1];
    return allPoints.length ? allPoints[allPoints.length - 1] : null;
  }, [allPoints]);

  const currentFg    = currentPoint?.fgSmoothed ?? null;
  const currentColor = currentFg != null ? fgColor(currentFg) : '#9ca3af';

  // Dynamic Y-axis domain: zoom to actual data range ±10 (clamped 0–100)
  const fgValues = useMemo(
    () => chartData.map(d => d.fgAll).filter((v): v is number => v != null),
    [chartData],
  );
  const fgDomainMin = fgValues.length ? Math.max(0,   Math.min(...fgValues) - 10) : 0;
  const fgDomainMax = fgValues.length ? Math.min(100, Math.max(...fgValues) + 10) : 100;

  const ihsgValues = chartData.map(p => p.ihsg).filter((v): v is number => v != null);
  const ihsgMin = ihsgValues.length ? Math.floor(Math.min(...ihsgValues) * 0.993 / 50) * 50 : 5000;
  const ihsgMax = ihsgValues.length ? Math.ceil(Math.max(...ihsgValues) * 1.007 / 50) * 50  : 8000;

  const xInterval = chartData.length > 60 ? Math.floor(chartData.length / 10)
                  : chartData.length > 30 ? Math.floor(chartData.length / 8)
                  : 'preserveStartEnd';

  const hasData = !loading && !error && chartData.length > 0;

  return (
    <div className="bg-white border border-[#e5e2db] rounded-2xl overflow-hidden">

      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div className="px-5 pt-4 pb-3">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-[#9ca3af] mb-0.5">
          Sentimen vs Pasar
        </p>
        <h2 className="text-sm font-bold text-[#0f172a]">Fear &amp; Greed vs IHSG</h2>
      </div>

      {/* ── Stats strip ───────────────────────────────────────────────────── */}
      {hasData && (
        <div className="flex flex-wrap items-center border-t border-[#f0ede8] py-2.5 gap-y-1.5 divide-x divide-[#f0ede8]">
          <StatItem
            label="Now"
            value={currentFg != null ? Math.round(currentFg) : null}
            sub={currentPoint?.label}
            color={currentFg != null ? getFGTextColor(currentFg) : '#9ca3af'}
          />
          <StatItem
            label="High"
            value={rangeStats.high != null ? Math.round(rangeStats.high) : null}
            sub={rangeStats.highDate ? formatDateShort(rangeStats.highDate) : undefined}
            color={rangeStats.high != null ? getFGTextColor(rangeStats.high) : '#9ca3af'}
          />
          <StatItem
            label="Low"
            value={rangeStats.low != null ? Math.round(rangeStats.low) : null}
            sub={rangeStats.lowDate ? formatDateShort(rangeStats.lowDate) : undefined}
            color={rangeStats.low != null ? getFGTextColor(rangeStats.low) : '#9ca3af'}
          />
        </div>
      )}

      {/* ── Loading / error / empty ────────────────────────────────────────── */}
      {loading && (
        <div className="h-56 flex items-center justify-center text-[#9ca3af] text-sm px-5 pb-5">
          <span className="animate-pulse">Memuat data…</span>
        </div>
      )}
      {error && (
        <div className="h-56 flex items-center justify-center text-[#9ca3af] text-sm px-5 pb-5">
          {error}
        </div>
      )}
      {!loading && !error && chartData.length === 0 && (
        <div className="h-56 flex items-center justify-center text-[#9ca3af] text-sm px-5 pb-5 text-center">
          Belum ada data historis.<br />
          Jalankan <code className="font-mono text-xs">compute_index.py</code> terlebih dahulu.
        </div>
      )}

      {/* ── Chart ─────────────────────────────────────────────────────────── */}
      {hasData && (
        <div className="px-2 pb-4 pt-1">
          <ResponsiveContainer width="100%" height={220}>
            <ComposedChart data={chartData} margin={{ top: 4, right: isMobile ? 8 : 54, bottom: 0, left: 0 }}>

              {/* Coinglass-style background: green bottom (fear/opportunity),
                  red top (greed/caution), clean white middle (neutral) */}
              <ReferenceArea yAxisId="fg" y1={0}  y2={40}  fill="#10B981" fillOpacity={0.08} stroke="none" />
              <ReferenceArea yAxisId="fg" y1={60} y2={100} fill="#EF4444" fillOpacity={0.08} stroke="none" />

              <CartesianGrid strokeDasharray="3 3" stroke="#f0ede8" vertical={false} />

              <XAxis
                dataKey="dateLabel"
                tick={{ fontSize: 10, fill: '#9ca3af' }}
                tickLine={false}
                axisLine={false}
                interval={xInterval}
              />

              {/* FIX 3: full range for "All"; zoomed for 1W/1M/3M */}
              <YAxis
                yAxisId="fg"
                domain={[fgDomainMin, fgDomainMax]}
                tick={{ fontSize: 10, fill: '#9ca3af' }}
                tickLine={false}
                axisLine={false}
                width={26}
              />
              <YAxis
                yAxisId="ihsg"
                orientation="right"
                domain={[ihsgMin, ihsgMax]}
                tick={isMobile ? false : { fontSize: 10, fill: '#d1cdc7' }}
                tickLine={false}
                axisLine={false}
                width={isMobile ? 0 : 46}
                tickFormatter={(v: number) =>
                  v >= 1000 ? (v / 1000).toFixed(1) + 'k' : String(v)
                }
              />

              <Tooltip content={<CustomTooltip />} />

              {/* IHSG — dark blue */}
              <Line
                yAxisId="ihsg"
                type="monotone"
                dataKey="ihsg"
                stroke="#1E40AF"
                strokeWidth={2}
                dot={false}
                connectNulls
                name="IHSG"
                opacity={0.7}
                activeDot={false}
              />

              {/* F&G — Customized draws one SVG <line> per point pair using
                  xAxisMap/yAxisMap scale functions. Tooltip still works because
                  IHSG payload[0].payload contains the full ChartPoint incl fgAll. */}
              <Customized component={FGColoredLine} />

            </ComposedChart>
          </ResponsiveContainer>

          {/* Legend */}
          <div className="flex items-center gap-4 mt-2 px-3 text-xs">
            <div className="flex items-center gap-1.5">
              <span className="inline-block w-5 rounded" style={{ height: 2.5, backgroundColor: currentColor }} />
              <span className="font-medium" style={{ color: currentColor }}>Fear &amp; Greed</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="inline-block w-5 rounded" style={{ height: 2, backgroundColor: '#1E40AF', opacity: 0.7 }} />
              <span style={{ color: '#1E40AF', opacity: 0.7 }}>IHSG</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
