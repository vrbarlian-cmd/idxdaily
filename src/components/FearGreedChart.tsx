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
} from 'recharts';
import type { FearGreedHistoryPoint } from '@/app/api/fear-greed-history/route';

// ── Types ─────────────────────────────────────────────────────────────────────

type Range = '1w' | '1m' | '3m' | 'all';

interface ChartPoint {
  rawDate:   string;
  dateLabel: string;
  fgAll:     number | null;   // full series — used for tooltip + backbone
  fg_ef:     number | null;   // Extreme Fear segment  (0–25)
  fg_fear:   number | null;   // Fear segment          (25–40)
  fg_neut:   number | null;   // Neutral segment       (40–60)
  fg_greed:  number | null;   // Greed segment         (60–75)
  fg_xg:     number | null;   // Extreme Greed segment (75–100)
  ihsg:      number | null;
  label:     string;
}

interface ApiResponse {
  points: FearGreedHistoryPoint[];
  days:   number;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const RANGES: { key: Range; label: string }[] = [
  { key: '1w',  label: '1W'  },
  { key: '1m',  label: '1M'  },
  { key: '3m',  label: '3M'  },
  { key: 'all', label: 'All' },
];

// Coinglass-style zone config: Fear=green (opportunity), Greed=red (caution)
const ZONES = [
  { min: 0,  max: 25,  key: 'fg_ef',    color: '#10B981', fill: '#10B981', opacity: 0.08, label: 'Ext. Fear'  },
  { min: 25, max: 40,  key: 'fg_fear',  color: '#34D399', fill: '#34D399', opacity: 0.07, label: 'Fear'       },
  { min: 40, max: 60,  key: 'fg_neut',  color: '#F59E0B', fill: '#F59E0B', opacity: 0.05, label: 'Neutral'    },
  { min: 60, max: 75,  key: 'fg_greed', color: '#F97316', fill: '#F97316', opacity: 0.08, label: 'Greed'      },
  { min: 75, max: 100, key: 'fg_xg',    color: '#EF4444', fill: '#EF4444', opacity: 0.10, label: 'Ext. Greed' },
] as const;

type ZoneKey = typeof ZONES[number]['key'];

// ── Helpers ───────────────────────────────────────────────────────────────────

function fgColor(score: number): string {
  if (score <= 25) return '#10B981';
  if (score <= 40) return '#34D399';
  if (score <= 60) return '#F59E0B';
  if (score <= 75) return '#F97316';
  return '#EF4444';
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

/** Assign a score value to a zone segment key — null if out of zone. */
function zoneValue(score: number | null, min: number, max: number): number | null {
  if (score === null) return null;
  return score >= min && score < max ? score : null;
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

// ── Main Component ────────────────────────────────────────────────────────────

export default function FearGreedChart() {
  const [allPoints, setAllPoints] = useState<FearGreedHistoryPoint[]>([]);
  const [range,     setRange]     = useState<Range>('3m');
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

  const filteredPoints = useMemo<FearGreedHistoryPoint[]>(() => {
    if (range === 'all') return allPoints;
    const days = range === '1w' ? 7 : range === '1m' ? 30 : 90;
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - days);
    cutoff.setHours(0, 0, 0, 0);
    return allPoints.filter(p => new Date(p.date + 'T00:00:00') >= cutoff);
  }, [allPoints, range]);

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

  // Build chart data: carry-forward IHSG for holidays + split F&G into zone keys
  const chartData = useMemo<ChartPoint[]>(() => {
    let lastIhsg: number | null = null;
    return filteredPoints.map(p => {
      if (p.ihsgClose !== null) lastIhsg = p.ihsgClose;
      const s = p.fgSmoothed;
      return {
        rawDate:   p.date,
        dateLabel: formatDateLabel(p.date),
        fgAll:     s,
        fg_ef:     zoneValue(s, 0,  25),
        fg_fear:   zoneValue(s, 25, 40),
        fg_neut:   zoneValue(s, 40, 60),
        fg_greed:  zoneValue(s, 60, 75),
        fg_xg:     zoneValue(s, 75, 101),  // 101 to include 100
        ihsg:      p.ihsgClose !== null ? p.ihsgClose : lastIhsg,
        label:     p.label,
      };
    });
  }, [filteredPoints]);

  const currentPoint = useMemo(() => {
    const live = filteredPoints.filter(p => !p.isBackfilled);
    if (live.length) return live[live.length - 1];
    return filteredPoints.length ? filteredPoints[filteredPoints.length - 1] : null;
  }, [filteredPoints]);

  const currentFg    = currentPoint?.fgSmoothed ?? null;
  const currentColor = currentFg != null ? fgColor(currentFg) : '#9ca3af';

  // FIX 3: full 0-100 for "All" view; dynamic ±10 zoom for shorter views
  const fgValues = useMemo(
    () => chartData.map(d => d.fgAll).filter((v): v is number => v != null),
    [chartData],
  );
  const fgDomainMin = range === 'all' ? 0
    : fgValues.length ? Math.max(0,   Math.min(...fgValues) - 10) : 0;
  const fgDomainMax = range === 'all' ? 100
    : fgValues.length ? Math.min(100, Math.max(...fgValues) + 10) : 100;

  const ihsgValues = chartData.map(p => p.ihsg).filter((v): v is number => v != null);
  const ihsgMin = ihsgValues.length ? Math.floor(Math.min(...ihsgValues) * 0.993 / 50) * 50 : 5000;
  const ihsgMax = ihsgValues.length ? Math.ceil(Math.max(...ihsgValues) * 1.007 / 50) * 50  : 8000;

  const xInterval = chartData.length > 60 ? Math.floor(chartData.length / 10)
                  : chartData.length > 30 ? Math.floor(chartData.length / 8)
                  : 'preserveStartEnd';

  // FIX 4: only show zone labels that are within the visible domain
  const visibleZones = ZONES.filter(z => z.max > fgDomainMin && z.min < fgDomainMax);

  const hasData = !loading && !error && chartData.length > 0;

  return (
    <div className="bg-white border border-[#e5e2db] rounded-2xl overflow-hidden">

      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-5 pt-4 pb-3 gap-3 flex-wrap">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-[#9ca3af] mb-0.5">
            Sentimen vs Pasar
          </p>
          <h2 className="text-sm font-bold text-[#0f172a]">Fear &amp; Greed vs IHSG</h2>
        </div>

        <div className="flex items-center gap-0.5 bg-[#f8f7f4] border border-[#e5e2db] rounded-lg p-0.5">
          {RANGES.map(r => (
            <button
              key={r.key}
              onClick={() => setRange(r.key)}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition-all ${
                range === r.key
                  ? 'bg-white text-[#0f172a] shadow-sm border border-[#e5e2db]'
                  : 'text-[#9ca3af] hover:text-[#374151]'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Stats strip ───────────────────────────────────────────────────── */}
      {hasData && (
        <div className="flex flex-wrap items-center border-t border-[#f0ede8] py-2.5 gap-y-1.5 divide-x divide-[#f0ede8]">
          <StatItem
            label="Now"
            value={currentFg != null ? Math.round(currentFg) : null}
            sub={currentPoint?.label}
            color={currentColor}
          />
          <StatItem
            label="High"
            value={rangeStats.high != null ? Math.round(rangeStats.high) : null}
            sub={rangeStats.highDate ? formatDateShort(rangeStats.highDate) : undefined}
            color="#047857"
          />
          <StatItem
            label="Low"
            value={rangeStats.low != null ? Math.round(rangeStats.low) : null}
            sub={rangeStats.lowDate ? formatDateShort(rangeStats.lowDate) : undefined}
            color="#b91c1c"
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

              {/* FIX 2: subtle zone background tints — always visible */}
              {visibleZones.map(z => (
                <ReferenceArea
                  key={z.key}
                  yAxisId="fg"
                  y1={z.min} y2={z.max}
                  fill={z.fill}
                  fillOpacity={z.opacity}
                  label={isMobile ? undefined : {
                    value: z.label,
                    position: 'insideRight',
                    fontSize: 9,
                    fill: z.color,
                    opacity: 0.65,
                    offset: 2,
                  }}
                />
              ))}

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

              {/* F&G backbone — thin neutral line ensures no visible gaps at zone boundaries */}
              <Line
                yAxisId="fg"
                type="monotone"
                dataKey="fgAll"
                stroke="#e5e7eb"
                strokeWidth={1}
                dot={false}
                connectNulls
                activeDot={false}
              />

              {/* FIX 1: zone-colored segments on top of backbone */}
              {ZONES.map(z => (
                <Line
                  key={z.key}
                  yAxisId="fg"
                  type="monotone"
                  dataKey={z.key as ZoneKey}
                  stroke={z.color}
                  strokeWidth={2.5}
                  dot={false}
                  connectNulls={false}
                  activeDot={{ r: 4, fill: z.color, stroke: 'white', strokeWidth: 2 }}
                />
              ))}

            </ComposedChart>
          </ResponsiveContainer>

          {/* Legend */}
          <div className="flex flex-wrap items-center justify-between mt-2 px-3 gap-y-1.5">
            <div className="flex items-center gap-4 text-xs">
              <div className="flex items-center gap-1.5">
                <span
                  className="inline-block w-5 rounded"
                  style={{ height: 2.5, backgroundColor: currentColor }}
                />
                <span className="font-medium" style={{ color: currentColor }}>
                  Fear &amp; Greed
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="inline-block w-5 rounded" style={{ height: 2, backgroundColor: '#1E40AF', opacity: 0.7 }} />
                <span style={{ color: '#1E40AF', opacity: 0.7 }}>IHSG</span>
              </div>
            </div>

            <div className="hidden sm:flex items-center gap-2 text-[10px]">
              {visibleZones.map(z => (
                <span key={z.key} className="flex items-center gap-1">
                  <span
                    className="inline-block w-3 h-1.5 rounded-sm"
                    style={{ backgroundColor: z.color, opacity: 0.7 }}
                  />
                  <span style={{ color: z.color }}>{z.label}</span>
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
