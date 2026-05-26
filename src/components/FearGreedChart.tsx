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
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts';
import { Activity, TrendingUp, TrendingDown } from 'lucide-react';
import type { FearGreedHistoryPoint } from '@/app/api/fear-greed-history/route';

// ── Types ─────────────────────────────────────────────────────────────────────

type Range = '1w' | '1m' | '3m' | 'all';

interface ChartPoint {
  rawDate:      string;
  dateLabel:    string;
  fgAll:        number | null;   // combined line (for tooltip, zone calculation)
  fgBackfill:   number | null;   // dashed line — backfilled only
  fgLive:       number | null;   // solid line — live only
  ihsg:         number | null;
  label:        string;
  isBackfilled: boolean;
}

interface ApiResponse {
  points: FearGreedHistoryPoint[];
  days:   number;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const RANGES: { key: Range; label: string }[] = [
  { key: '1w',  label: '1 Week'    },
  { key: '1m',  label: '1 Month'   },
  { key: '3m',  label: '3 Months'  },
  { key: 'all', label: 'All'       },
];

const ZONES = [
  { y1: 0,  y2: 25,  fill: '#fef2f2', label: 'Ext. Fear',  labelColor: '#dc2626' },
  { y1: 25, y2: 45,  fill: '#fff7ed', label: 'Fear',        labelColor: '#ea580c' },
  { y1: 45, y2: 55,  fill: '#fefce8', label: 'Neutral',     labelColor: '#ca8a04' },
  { y1: 55, y2: 75,  fill: '#f7fee7', label: 'Greed',       labelColor: '#65a30d' },
  { y1: 75, y2: 100, fill: '#f0fdf4', label: 'Ext. Greed',  labelColor: '#16a34a' },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function fgColor(score: number): string {
  if (score >= 75) return '#10b981';
  if (score >= 55) return '#84cc16';
  if (score >= 45) return '#eab308';
  if (score >= 25) return '#f97316';
  return '#ef4444';
}

function formatDateLabel(dateStr: string, totalDays: number): string {
  const d = new Date(dateStr + 'T00:00:00');
  if (totalDays > 60) {
    return d.toLocaleDateString('id-ID', { day: 'numeric', month: 'short' });
  }
  return d.toLocaleDateString('id-ID', { day: 'numeric', month: 'short' });
}

function formatDateShort(dateStr: string | null): string {
  if (!dateStr) return '—';
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('id-ID', { day: 'numeric', month: 'short' });
}

function daysFromNow(dateStr: string): number {
  const d = new Date(dateStr + 'T00:00:00');
  const now = new Date();
  return Math.floor((now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
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

  // Get the actual fg value and label from the first payload that has data
  const pt = payload[0]?.payload as ChartPoint | undefined;
  if (!pt) return null;

  const fgVal = pt.fgAll;
  const ihsgVal = pt.ihsg;
  const fgLabel = pt.label;

  return (
    <div className="bg-white/95 backdrop-blur-sm border border-stone-200 rounded-xl shadow-lg p-3 text-xs min-w-[140px]">
      <p className="font-semibold text-stone-600 mb-2 pb-1.5 border-b border-stone-100">{label}</p>

      {fgVal != null && (
        <div className="flex items-center justify-between gap-3 mb-1">
          <span className="text-stone-500">Fear &amp; Greed</span>
          <span className="font-bold tabular-nums" style={{ color: fgColor(fgVal) }}>
            {fgVal.toFixed(1)}
          </span>
        </div>
      )}
      {fgLabel && fgVal != null && (
        <div className="flex items-center justify-between gap-3 mb-1">
          <span className="text-stone-400">Status</span>
          <span className="font-medium" style={{ color: fgColor(fgVal) }}>{fgLabel}</span>
        </div>
      )}
      {ihsgVal != null && (
        <div className="flex items-center justify-between gap-3 mt-1.5 pt-1.5 border-t border-stone-100">
          <span className="text-stone-500">IHSG</span>
          <span className="font-semibold text-slate-600 tabular-nums">
            {Math.round(ihsgVal).toLocaleString('id-ID')}
          </span>
        </div>
      )}
      {pt.isBackfilled && (
        <p className="text-stone-300 mt-1.5 text-[10px]">Data rekonstruksi</p>
      )}
    </div>
  );
}

// ── Stat Card ─────────────────────────────────────────────────────────────────

function StatMini({
  label, value, sub, color,
}: {
  label: string;
  value: string | number | null;
  sub?:  string;
  color?: string;
}) {
  return (
    <div className="flex-1 min-w-0 text-center">
      <p className="text-[10px] text-stone-400 uppercase tracking-wider mb-0.5">{label}</p>
      <p
        className="text-xl font-bold leading-none tabular-nums"
        style={{ color: color ?? '#1c1917' }}
      >
        {value ?? '—'}
      </p>
      {sub && <p className="text-[10px] text-stone-400 mt-0.5">{sub}</p>}
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function FearGreedChart() {
  const [allPoints, setAllPoints] = useState<FearGreedHistoryPoint[]>([]);
  const [range,     setRange]     = useState<Range>('3m');
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState<string | null>(null);
  const [isMobile,  setIsMobile]  = useState(false);

  // Detect mobile viewport
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 640);
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  // Fetch all data once; filter client-side for range toggles
  useEffect(() => {
    fetch('/api/fear-greed-history?days=all')
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<ApiResponse>;
      })
      .then(d => {
        setAllPoints(d.points);
        setLoading(false);
      })
      .catch(() => {
        setError('Gagal memuat data historis');
        setLoading(false);
      });
  }, []);

  // Filter points by selected range
  const filteredPoints = useMemo<FearGreedHistoryPoint[]>(() => {
    if (range === 'all') return allPoints;
    const days = range === '1w' ? 7 : range === '1m' ? 30 : 90;
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - days);
    cutoff.setHours(0, 0, 0, 0);
    return allPoints.filter(p => new Date(p.date + 'T00:00:00') >= cutoff);
  }, [allPoints, range]);

  // High/low/date computed from the visible (range-filtered) points
  const rangeStats = useMemo(() => {
    let high = -Infinity, highDate = '';
    let low  =  Infinity, lowDate  = '';
    for (const p of filteredPoints) {
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
  }, [filteredPoints]);

  // Human-readable label for the active range (used in stat card labels)
  const rangeLabel = range === '1w' ? '1 Week' : range === '1m' ? '1 Month' : range === '3m' ? '3 Months' : 'All';

  // Build chart data — split fgBackfill / fgLive, include seam overlap
  const { chartData, firstLiveIdx, transitionLabel } = useMemo(() => {
    if (!filteredPoints.length) {
      return { chartData: [], firstLiveIdx: -1, transitionLabel: null };
    }

    const totalDays = filteredPoints.length;
    // Find where data transitions from backfilled to live
    const fli = filteredPoints.findIndex(p => !p.isBackfilled);

    const data: ChartPoint[] = filteredPoints.map((p, i) => {
      const label = formatDateLabel(p.date, totalDays);
      const fg = p.fgSmoothed;

      // Seam: include the boundary point in both series so lines connect
      const isBoundaryBackfill = p.isBackfilled && i === fli - 1;
      const isBoundaryLive     = !p.isBackfilled && i === fli;

      return {
        rawDate:      p.date,
        dateLabel:    label,
        fgAll:        fg,
        fgBackfill:   (p.isBackfilled || isBoundaryLive) ? fg : null,
        fgLive:       (!p.isBackfilled || isBoundaryBackfill) ? fg : null,
        ihsg:         p.ihsgClose,
        label:        p.label,
        isBackfilled: p.isBackfilled,
      };
    });

    const transLabel = fli > 0 ? data[fli]?.dateLabel ?? null : null;

    return { chartData: data, firstLiveIdx: fli, transitionLabel: transLabel };
  }, [filteredPoints]);

  // Current value (last live point, or last backfill if no live)
  const currentPoint = useMemo(() => {
    const live = filteredPoints.filter(p => !p.isBackfilled);
    if (live.length) return live[live.length - 1];
    const all = filteredPoints;
    return all.length ? all[all.length - 1] : null;
  }, [filteredPoints]);

  const currentFg = currentPoint?.fgSmoothed ?? null;
  const currentColor = currentFg != null ? fgColor(currentFg) : '#a8a29e';

  // IHSG Y-axis domain
  const ihsgValues = chartData.map(p => p.ihsg).filter((v): v is number => v != null);
  const ihsgMin = ihsgValues.length ? Math.floor(Math.min(...ihsgValues) * 0.993 / 50) * 50 : 5000;
  const ihsgMax = ihsgValues.length ? Math.ceil(Math.max(...ihsgValues) * 1.007 / 50) * 50  : 8000;

  // X-axis interval — avoid crowding
  const xInterval = chartData.length > 60 ? Math.floor(chartData.length / 10)
                  : chartData.length > 30 ? Math.floor(chartData.length / 8)
                  : 'preserveStartEnd';

  const hasData = !loading && !error && chartData.length > 0;
  const hasBackfill = firstLiveIdx > 0;
  const hasLive = firstLiveIdx !== -1;

  return (
    <div className="bg-white border border-stone-200 rounded-2xl shadow-sm overflow-hidden">

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-5 pt-5 pb-3 flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-stone-400 flex-shrink-0" />
          <h2 className="text-base font-semibold text-stone-900">
            Fear &amp; Greed vs IHSG
          </h2>
        </div>

        {/* Range toggle */}
        <div className="flex items-center gap-1 bg-stone-100 rounded-lg p-0.5">
          {RANGES.map(r => (
            <button
              key={r.key}
              onClick={() => setRange(r.key)}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition-all ${
                range === r.key
                  ? 'bg-white text-stone-900 shadow-sm'
                  : 'text-stone-500 hover:text-stone-700'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Stats row ───────────────────────────────────────────────────────── */}
      {hasData && (
        <div className="flex items-stretch divide-x divide-stone-100 px-5 pb-4">
          <StatMini
            label="Now"
            value={currentFg != null ? Math.round(currentFg) : null}
            sub={currentPoint?.label}
            color={currentColor}
          />
          <div className="w-px" />
          <StatMini
            label={isMobile ? 'High' : `Highest (${rangeLabel})`}
            value={rangeStats.high != null ? Math.round(rangeStats.high) : null}
            sub={rangeStats.highDate ? formatDateShort(rangeStats.highDate) : undefined}
            color="#10b981"
          />
          <div className="w-px" />
          <StatMini
            label={isMobile ? 'Low' : `Lowest (${rangeLabel})`}
            value={rangeStats.low != null ? Math.round(rangeStats.low) : null}
            sub={rangeStats.lowDate ? formatDateShort(rangeStats.lowDate) : undefined}
            color="#ef4444"
          />
        </div>
      )}

      {/* ── States ──────────────────────────────────────────────────────────── */}
      {loading && (
        <div className="h-56 flex items-center justify-center text-stone-400 text-sm px-5 pb-5">
          <span className="animate-pulse">Memuat data…</span>
        </div>
      )}
      {error && (
        <div className="h-56 flex items-center justify-center text-stone-400 text-sm px-5 pb-5">
          {error}
        </div>
      )}
      {!loading && !error && chartData.length === 0 && (
        <div className="h-56 flex items-center justify-center text-stone-400 text-sm px-5 pb-5 text-center">
          Belum ada data historis.
          <br />
          Jalankan <code className="font-mono text-xs">compute_index.py</code> terlebih dahulu.
        </div>
      )}

      {/* ── Chart ───────────────────────────────────────────────────────────── */}
      {hasData && (
        <div className="px-2 pb-4">
          <ResponsiveContainer width="100%" height={230}>
            <ComposedChart data={chartData} margin={{ top: 6, right: isMobile ? 8 : 56, bottom: 0, left: 0 }}>

              {/* Zone bands */}
              {ZONES.map(z => (
                <ReferenceArea
                  key={z.label}
                  yAxisId="fg"
                  y1={z.y1}
                  y2={z.y2}
                  fill={z.fill}
                  fillOpacity={0.7}
                  label={isMobile ? undefined : {
                    value: z.label,
                    position: 'insideRight',
                    fontSize: 9,
                    fill: z.labelColor,
                    opacity: 0.6,
                    offset: 2,
                  }}
                />
              ))}

              {/* Backfill→Live transition marker */}
              {hasBackfill && hasLive && transitionLabel && (
                <ReferenceLine
                  yAxisId="fg"
                  x={transitionLabel}
                  stroke="#d1d5db"
                  strokeDasharray="3 2"
                  strokeWidth={1}
                  label={{
                    value: 'Live →',
                    position: 'insideTopRight',
                    fontSize: 9,
                    fill: '#9ca3af',
                    offset: 4,
                  }}
                />
              )}

              <CartesianGrid strokeDasharray="3 3" stroke="#f5f5f4" vertical={false} />

              <XAxis
                dataKey="dateLabel"
                tick={{ fontSize: 10, fill: '#a8a29e' }}
                tickLine={false}
                axisLine={false}
                interval={xInterval}
              />

              {/* Left axis: F&G 0–100 */}
              <YAxis
                yAxisId="fg"
                domain={[0, 100]}
                tick={{ fontSize: 10, fill: '#a8a29e' }}
                tickLine={false}
                axisLine={false}
                width={26}
                ticks={[0, 25, 50, 75, 100]}
              />

              {/* Right axis: IHSG price — hidden on mobile to save space */}
              <YAxis
                yAxisId="ihsg"
                orientation="right"
                domain={[ihsgMin, ihsgMax]}
                tick={isMobile ? false : { fontSize: 10, fill: '#cbd5e1' }}
                tickLine={false}
                axisLine={false}
                width={isMobile ? 0 : 46}
                tickFormatter={(v: number) =>
                  v >= 1000 ? (v / 1000).toFixed(1) + 'k' : String(v)
                }
              />

              <Tooltip content={<CustomTooltip />} />

              {/* IHSG line — behind F&G */}
              <Line
                yAxisId="ihsg"
                type="monotone"
                dataKey="ihsg"
                stroke="#cbd5e1"
                strokeWidth={1.5}
                dot={false}
                connectNulls
                name="IHSG"
              />

              {/* F&G backfilled line — dashed, medium blue */}
              {hasBackfill && (
                <Line
                  yAxisId="fg"
                  type="monotone"
                  dataKey="fgBackfill"
                  stroke="#60a5fa"
                  strokeWidth={2.5}
                  strokeDasharray="5 3"
                  strokeOpacity={0.7}
                  dot={false}
                  connectNulls
                  name="F&G (rekonstruksi)"
                />
              )}

              {/* F&G live line — solid, deep blue, thick */}
              <Line
                yAxisId="fg"
                type="monotone"
                dataKey="fgLive"
                stroke="#1d4ed8"
                strokeWidth={3}
                dot={false}
                connectNulls
                name="Fear & Greed"
                activeDot={{ r: 5, fill: '#1d4ed8', stroke: 'white', strokeWidth: 2 }}
              />

            </ComposedChart>
          </ResponsiveContainer>

          {/* ── Legend ──────────────────────────────────────────────────────── */}
          <div className="flex flex-wrap items-center justify-between mt-1 px-3 gap-y-2">
            <div className="flex items-center gap-4 text-xs">
              {/* F&G live */}
              <div className="flex items-center gap-1.5">
                <span className="inline-block w-5 border-t-[3px] border-blue-700 rounded" />
                <span className="text-stone-600 font-medium">Fear &amp; Greed</span>
              </div>
              {/* F&G backfill */}
              {hasBackfill && (
                <div className="flex items-center gap-1.5">
                  <svg width="20" height="2" className="overflow-visible">
                    <line
                      x1="0" y1="1" x2="20" y2="1"
                      stroke="#60a5fa"
                      strokeWidth="2.5"
                      strokeDasharray="5 3"
                      strokeOpacity="0.7"
                    />
                  </svg>
                  <span className="text-stone-400">Rekonstruksi</span>
                </div>
              )}
              {/* IHSG */}
              <div className="flex items-center gap-1.5">
                <span className="inline-block w-5 border-t border-slate-300 rounded" />
                <span className="text-stone-400">IHSG</span>
              </div>
            </div>

            {/* Zone color key */}
            <div className="flex items-center gap-1.5 text-[10px] text-stone-300">
              {ZONES.map(z => (
                <span
                  key={z.label}
                  className="flex items-center gap-0.5"
                  title={z.label}
                >
                  <span
                    className="inline-block w-2.5 h-2.5 rounded-sm border"
                    style={{
                      backgroundColor: z.fill,
                      borderColor: z.labelColor + '40',
                    }}
                  />
                  <span style={{ color: z.labelColor + 'aa' }}>
                    {z.label.split(' ')[0]}
                  </span>
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
