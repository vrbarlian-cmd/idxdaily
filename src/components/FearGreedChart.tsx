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
  fgAll:     number | null;
  ihsg:      number | null;
  label:     string;
}

// Each zone gets its own array — every point has val in exactly one zone
interface ZonePoint extends ChartPoint {
  val: number | null;
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

// Zone color + legend reference (strict < boundaries, no overlap)
const LINE_ZONES = [
  { threshold: [0,  25], color: '#059669', label: 'Ext. Fear'  },
  { threshold: [25, 40], color: '#34D399', label: 'Fear'       },
  { threshold: [40, 60], color: '#F59E0B', label: 'Neutral'    },
  { threshold: [60, 75], color: '#F97316', label: 'Greed'      },
  { threshold: [75, 100],color: '#DC2626', label: 'Ext. Greed' },
] as const;

// Background zones (2 only) — fear zone green, greed zone red, no neutral bg
const BG_ZONES = [
  { y1: 0,  y2: 40,  fill: '#10B981', opacity: 0.06, label: 'Fear / Peluang' },
  { y1: 60, y2: 100, fill: '#EF4444', opacity: 0.06, label: 'Greed / Waspada' },
] as const;

// ── Helpers ───────────────────────────────────────────────────────────────────

// Line color: contrarian (Fear=green=opportunity, Greed=red=caution)
function fgColor(score: number): string {
  if (score <= 25) return '#059669';  // Extreme Fear  — dark green
  if (score <= 40) return '#34D399';  // Fear          — light green
  if (score <= 60) return '#F59E0B';  // Neutral       — yellow
  if (score <= 75) return '#F97316';  // Greed         — orange
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

  // Build chart data — carry-forward IHSG for holidays, no zone keys
  const chartData = useMemo<ChartPoint[]>(() => {
    let lastIhsg: number | null = null;
    return filteredPoints.map(p => {
      if (p.ihsgClose !== null) lastIhsg = p.ihsgClose;
      return {
        rawDate:   p.date,
        dateLabel: formatDateLabel(p.date),
        fgAll:     p.fgSmoothed,
        ihsg:      p.ihsgClose !== null ? p.ihsgClose : lastIhsg,
        label:     p.label,
      };
    });
  }, [filteredPoints]);

  // Zone data — 5 separate arrays, every point in exactly ONE zone (no backbone needed)
  const zoneData = useMemo(() => {
    const ef:      ZonePoint[] = [];
    const fear:    ZonePoint[] = [];
    const neutral: ZonePoint[] = [];
    const greed:   ZonePoint[] = [];
    const eg:      ZonePoint[] = [];

    for (const pt of chartData) {
      const s = pt.fgAll;
      if (s === null) {
        ef.push({ ...pt, val: null });
        fear.push({ ...pt, val: null });
        neutral.push({ ...pt, val: null });
        greed.push({ ...pt, val: null });
        eg.push({ ...pt, val: null });
      } else if (s < 25) {
        ef.push({ ...pt, val: s }); fear.push({ ...pt, val: null });
        neutral.push({ ...pt, val: null }); greed.push({ ...pt, val: null }); eg.push({ ...pt, val: null });
      } else if (s < 40) {
        ef.push({ ...pt, val: null }); fear.push({ ...pt, val: s });
        neutral.push({ ...pt, val: null }); greed.push({ ...pt, val: null }); eg.push({ ...pt, val: null });
      } else if (s < 60) {
        ef.push({ ...pt, val: null }); fear.push({ ...pt, val: null });
        neutral.push({ ...pt, val: s }); greed.push({ ...pt, val: null }); eg.push({ ...pt, val: null });
      } else if (s < 75) {
        ef.push({ ...pt, val: null }); fear.push({ ...pt, val: null });
        neutral.push({ ...pt, val: null }); greed.push({ ...pt, val: s }); eg.push({ ...pt, val: null });
      } else {
        ef.push({ ...pt, val: null }); fear.push({ ...pt, val: null });
        neutral.push({ ...pt, val: null }); greed.push({ ...pt, val: null }); eg.push({ ...pt, val: s });
      }
    }
    return { ef, fear, neutral, greed, eg };
  }, [chartData]);

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

  // Visible line zones for legend (within current domain)
  const visibleLineZones = LINE_ZONES.filter(
    z => z.threshold[1] > fgDomainMin && z.threshold[0] < fgDomainMax
  );
  // Background zones clipped to visible domain
  const visibleBgZones = BG_ZONES.filter(z => z.y2 > fgDomainMin && z.y1 < fgDomainMax);

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

              {/* FIX 2: only 2 background tints — fear (green) and greed (red) */}
              {visibleBgZones.map(z => (
                <ReferenceArea
                  key={z.label}
                  yAxisId="fg"
                  y1={z.y1} y2={z.y2}
                  fill={z.fill}
                  fillOpacity={z.opacity}
                  label={isMobile ? undefined : {
                    value: z.label,
                    position: 'insideRight',
                    fontSize: 9,
                    fill: z.fill,
                    opacity: 0.55,
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

              {/* F&G — 5 zone Lines, each with its own data array.
                  Every point is in exactly ONE zone → no backbone needed,
                  no gray bleed, no boundary fallthrough. */}
              <Line yAxisId="fg" type="monotone" dataKey="val"
                data={zoneData.ef}      stroke="#059669" strokeWidth={2.5}
                dot={false} connectNulls={false}
                activeDot={{ r: 4, fill: '#059669', stroke: 'white', strokeWidth: 2 }} />
              <Line yAxisId="fg" type="monotone" dataKey="val"
                data={zoneData.fear}    stroke="#34D399" strokeWidth={2.5}
                dot={false} connectNulls={false}
                activeDot={{ r: 4, fill: '#34D399', stroke: 'white', strokeWidth: 2 }} />
              <Line yAxisId="fg" type="monotone" dataKey="val"
                data={zoneData.neutral} stroke="#F59E0B" strokeWidth={2.5}
                dot={false} connectNulls={false}
                activeDot={{ r: 4, fill: '#F59E0B', stroke: 'white', strokeWidth: 2 }} />
              <Line yAxisId="fg" type="monotone" dataKey="val"
                data={zoneData.greed}   stroke="#F97316" strokeWidth={2.5}
                dot={false} connectNulls={false}
                activeDot={{ r: 4, fill: '#F97316', stroke: 'white', strokeWidth: 2 }} />
              <Line yAxisId="fg" type="monotone" dataKey="val"
                data={zoneData.eg}      stroke="#DC2626" strokeWidth={2.5}
                dot={false} connectNulls={false}
                activeDot={{ r: 4, fill: '#DC2626', stroke: 'white', strokeWidth: 2 }} />

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
              {visibleLineZones.map(z => (
                <span key={z.label} className="flex items-center gap-1">
                  <span
                    className="inline-block w-3 h-1.5 rounded-sm"
                    style={{ backgroundColor: z.color, opacity: 0.8 }}
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
