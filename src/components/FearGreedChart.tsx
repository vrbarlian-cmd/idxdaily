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

// Single sophisticated teal accent — clean, high-end financial journalism look
const FG_COLOR = '#0d9488';

// Coinglass-style zone fills: faint green bottom (fear), faint red top (greed)
const ZONES = [
  { y1: 0,  y2: 25,  fill: '#ecfdf5', label: 'Ext. Fear',  labelColor: '#059669' },
  { y1: 25, y2: 45,  fill: '#f7fef9', label: 'Fear',        labelColor: '#6ee7b7' },
  { y1: 45, y2: 55,  fill: '#fafafa', label: 'Neutral',     labelColor: '#9ca3af' },
  { y1: 55, y2: 75,  fill: '#fff8f1', label: 'Greed',       labelColor: '#fb923c' },
  { y1: 75, y2: 100, fill: '#fff1f2', label: 'Ext. Greed',  labelColor: '#f87171' },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function fgColor(score: number): string {
  if (score >= 75) return '#047857';
  if (score >= 55) return '#059669';
  if (score >= 45) return '#6b7280';
  if (score >= 25) return '#d97706';
  return '#b91c1c';
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

  // Single unified series — no backfill/live split
  const chartData = useMemo<ChartPoint[]>(() => {
    return filteredPoints.map(p => ({
      rawDate:   p.date,
      dateLabel: formatDateLabel(p.date),
      fgAll:     p.fgSmoothed,
      ihsg:      p.ihsgClose,
      label:     p.label,
    }));
  }, [filteredPoints]);

  const currentPoint = useMemo(() => {
    const live = filteredPoints.filter(p => !p.isBackfilled);
    if (live.length) return live[live.length - 1];
    return filteredPoints.length ? filteredPoints[filteredPoints.length - 1] : null;
  }, [filteredPoints]);

  const currentFg    = currentPoint?.fgSmoothed ?? null;
  const currentColor = currentFg != null ? fgColor(currentFg) : '#9ca3af';

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
            <ComposedChart data={chartData} margin={{ top: 4, right: isMobile ? 8 : 52, bottom: 0, left: 0 }}>

              {/*
                Coinglass-style gradient: top of chart = Extreme Greed = muted red/pink,
                bottom = Extreme Fear = desaturated green. Stops match zone boundaries
                (score 100→75→55→45→25→0 maps to y 0%→25%→45%→55%→75%→100%).
              */}
              <defs>
                <linearGradient id="fgLineGradient" x1="0" y1="0" x2="0" y2="1">
                  {/* top=score100=Extreme Greed → bottom=score0=Extreme Fear */}
                  {/* Duplicate stops at boundaries create Coinglass-style hard color edges */}
                  <stop offset="0%"   stopColor="#F6465D" />  {/* Extreme Greed */}
                  <stop offset="25%"  stopColor="#F6465D" />
                  <stop offset="25%"  stopColor="#F4742B" />  {/* Greed */}
                  <stop offset="45%"  stopColor="#F4742B" />
                  <stop offset="45%"  stopColor="#F0B90B" />  {/* Neutral */}
                  <stop offset="50%"  stopColor="#F0B90B" />
                  <stop offset="50%"  stopColor="#84CC9A" />  {/* Fear */}
                  <stop offset="75%"  stopColor="#84CC9A" />
                  <stop offset="75%"  stopColor="#00C076" />  {/* Extreme Fear */}
                  <stop offset="100%" stopColor="#00C076" />
                </linearGradient>
              </defs>

              {/* Zone bands */}
              {ZONES.map(z => (
                <ReferenceArea
                  key={z.label}
                  yAxisId="fg"
                  y1={z.y1} y2={z.y2}
                  fill={z.fill}
                  fillOpacity={1}
                  label={isMobile ? undefined : {
                    value: z.label,
                    position: 'insideRight',
                    fontSize: 9,
                    fill: z.labelColor,
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
              <YAxis
                yAxisId="fg"
                domain={[0, 100]}
                tick={{ fontSize: 10, fill: '#9ca3af' }}
                tickLine={false}
                axisLine={false}
                width={26}
                ticks={[0, 25, 50, 75, 100]}
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

              {/* IHSG — muted warm gray, behind F&G */}
              <Line
                yAxisId="ihsg"
                type="monotone"
                dataKey="ihsg"
                stroke="#d1cdc7"
                strokeWidth={1.5}
                dot={false}
                connectNulls
                name="IHSG"
                opacity={0.8}
              />

              {/* F&G — Coinglass-style segmented gradient line, semi-transparent */}
              <Line
                yAxisId="fg"
                type="monotone"
                dataKey="fgAll"
                stroke="url(#fgLineGradient)"
                strokeWidth={2.5}
                dot={false}
                connectNulls
                name="Fear & Greed"
                activeDot={{ r: 4, fill: '#6b7280', stroke: 'white', strokeWidth: 2 }}
              />

            </ComposedChart>
          </ResponsiveContainer>

          {/* Legend */}
          <div className="flex flex-wrap items-center justify-between mt-2 px-3 gap-y-1.5">
            <div className="flex items-center gap-4 text-xs">
              <div className="flex items-center gap-1.5">
                <svg width="20" height="3" style={{ overflow: 'visible', display: 'block' }}>
                  <defs>
                    <linearGradient id="legendFgGrad" x1="0" y1="0" x2="1" y2="0">
                      <stop offset="0%"   stopColor="#00C076" />
                      <stop offset="50%"  stopColor="#F0B90B" />
                      <stop offset="100%" stopColor="#F6465D" />
                    </linearGradient>
                  </defs>
                  <line x1="0" y1="1.5" x2="20" y2="1.5" stroke="url(#legendFgGrad)" strokeWidth="2.5" />
                </svg>
                <span className="text-[#6b7280] font-medium">Fear &amp; Greed</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="inline-block w-5 border-t border-[#d1cdc7] rounded" />
                <span className="text-[#9ca3af]">IHSG</span>
              </div>
            </div>

            <div className="hidden sm:flex items-center gap-1.5 text-[10px]">
              {ZONES.map(z => (
                <span key={z.label} className="flex items-center gap-0.5" title={z.label}>
                  <span
                    className="inline-block w-2 h-2 rounded-sm"
                    style={{ backgroundColor: z.fill, border: `1px solid ${z.labelColor}40` }}
                  />
                  <span style={{ color: z.labelColor + 'bb' }}>{z.label.split(' ')[0]}</span>
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
