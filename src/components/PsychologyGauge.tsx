'use client';

import { useEffect, useState } from 'react';
import { zoneColors } from '@/lib/zoneColors';
import type { PsychologyIndexData } from '@/app/api/psychology-index/route';

// ── Minimal SVG gauge (matches FearGreedGauge design) ─────────────────────────

function GaugeSVG({ score, isNull }: { score: number; isNull: boolean }) {
  const cx = 150, cy = 150, r = 120;
  const needleLen = 105, tipR = 12, pivotR = 8;
  const arcLen    = Math.PI * r;
  const arcPath   = `M 30 ${cy} A ${r} ${r} 0 0 1 270 ${cy}`;
  const needleDeg = -90 + (score / 100) * 180;

  const { hex } = zoneColors(isNull ? null : score);

  const tipText = isNull ? '—' : String(Math.round(score));
  const tipFs   = tipText.length > 2 ? 8 : 10;

  return (
    <svg viewBox="0 0 300 170" className="w-full" aria-hidden="true">
      <defs>
        <linearGradient id="arcGradB" gradientUnits="userSpaceOnUse" x1="30" y1="0" x2="270" y2="0">
          <stop offset="0%"   stopColor="#ef4444" />
          <stop offset="25%"  stopColor="#f97316" />
          <stop offset="50%"  stopColor="#eab308" />
          <stop offset="75%"  stopColor="#84cc16" />
          <stop offset="100%" stopColor="#10b981" />
        </linearGradient>
        <filter id="glowNeedleB">
          <feGaussianBlur stdDeviation="1.5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Track */}
      <path d={arcPath} fill="none" stroke="#e7e5e4" strokeWidth="20" strokeLinecap="round" />

      {/* Filled arc */}
      <path
        d={arcPath}
        fill="none"
        stroke="url(#arcGradB)"
        strokeWidth="20"
        strokeLinecap="round"
        strokeDasharray={`${(score / 100) * arcLen} ${arcLen}`}
      />

      {/* Needle */}
      <g transform={`rotate(${needleDeg}, ${cx}, ${cy})`} filter="url(#glowNeedleB)">
        <line
          x1={cx} y1={cy} x2={cx} y2={cy - needleLen}
          stroke="#292524" strokeWidth="2.5" strokeLinecap="round"
        />
        <circle cx={cx} cy={cy - needleLen} r={tipR} fill={hex} />
        <text
          x={cx} y={cy - needleLen}
          textAnchor="middle" dominantBaseline="central"
          fontSize={tipFs} fill="white" fontWeight="700"
          fontFamily="ui-sans-serif, system-ui, sans-serif"
        >
          {tipText}
        </text>
      </g>

      {/* Pivot */}
      <circle cx={cx} cy={cy} r={pivotR} fill="#292524" />

      {/* Zone labels */}
      <text x="30"  y="168" textAnchor="start" fontSize="9" fill="#a8a29e"
        fontFamily="ui-sans-serif, system-ui, sans-serif">
        Extreme Fear
      </text>
      <text x="270" y="168" textAnchor="end" fontSize="9" fill="#a8a29e"
        fontFamily="ui-sans-serif, system-ui, sans-serif">
        Extreme Greed
      </text>
    </svg>
  );
}

// ── Empty state when no rows in DB yet ────────────────────────────────────────

function EmptyState() {
  return (
    <div className="bg-white border border-stone-200 rounded-2xl p-5 shadow-sm">
      <div>
        <h2 className="text-base font-bold text-stone-900">Psikologi Pasar</h2>
        <p className="text-xs text-stone-500 mt-0.5">Indeks sentimen investor domestik</p>
      </div>
      <div className="border-t border-stone-100 my-3" />
      <div className="flex flex-col items-center justify-center py-8 text-center gap-3">
        <div className="w-12 h-12 rounded-full bg-stone-100 flex items-center justify-center text-2xl">
          📊
        </div>
        <p className="text-sm font-semibold text-stone-700">Data psikologi belum tersedia</p>
        <p className="text-xs text-stone-400 max-w-xs leading-relaxed">
          Masukkan data aliran domestik harian via terminal untuk mulai melacak sentimen investor lokal.
        </p>
        <code className="text-xs bg-stone-100 text-stone-600 rounded px-3 py-1.5 font-mono">
          python -m backend.scripts.set_domestic_flow --buy … --sell …
        </code>
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function PsychologyGauge() {
  const [data, setData]     = useState<PsychologyIndexData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/psychology-index')
      .then(r => r.json())
      .then((d: PsychologyIndexData) => {
        setData(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  // Loading skeleton
  if (loading) {
    return (
      <div className="bg-white border border-stone-200 rounded-2xl p-5 shadow-sm animate-pulse">
        <div className="h-4 w-40 bg-stone-200 rounded mb-2" />
        <div className="h-3 w-32 bg-stone-100 rounded mb-4" />
        <div className="h-32 bg-stone-100 rounded-xl" />
      </div>
    );
  }

  // No data at all
  if (!data || data.score === null) {
    return <EmptyState />;
  }

  const displayScore = data.score ?? 50;
  const { text, bg, hex } = zoneColors(data.score);
  const isLimitedData = data.daysOfRetailData < 5;

  // Retail direction label
  const directionLabel = data.retailDirection === 1
    ? 'Net Beli'
    : data.retailDirection === -1
    ? 'Net Jual'
    : 'Flat';

  const wib = new Date().toLocaleTimeString('id-ID', {
    hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Jakarta',
  });

  return (
    <div className="bg-white border border-stone-200 rounded-2xl p-5 shadow-sm">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-base font-bold text-stone-900">Psikologi Pasar</h2>
          <p className="text-xs text-stone-500 mt-0.5">
            Sentimen investor domestik · {data.activeComponents}/5 komponen
          </p>
        </div>
        {/* Limited data badge */}
        {isLimitedData && (
          <span className="text-xs bg-amber-50 text-amber-600 border border-amber-200 rounded-full px-2 py-0.5 flex-shrink-0">
            data terbatas ({data.daysOfRetailData}h)
          </span>
        )}
      </div>

      <div className="border-t border-stone-100 my-3" />

      {/* Gauge SVG */}
      <GaugeSVG score={displayScore} isNull={data.score == null} />

      {/* Score */}
      <div className="text-center -mt-1 mb-3 relative">
        {data.score != null && (
          <div
            className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-24 h-24 rounded-full blur-3xl pointer-events-none"
            style={{ backgroundColor: hex, opacity: 0.18 }}
          />
        )}
        <p
          className={`text-5xl font-bold leading-none tabular-nums relative ${text}`}
          style={data.score != null ? { filter: `drop-shadow(0 0 6px ${hex}55)` } : {}}
        >
          {data.score != null ? Math.round(data.score) : '—'}
        </p>
        <span className={`inline-block mt-2.5 px-4 py-1 rounded-full text-xs font-bold text-white ${bg}`}>
          {data.label}
        </span>
      </div>

      {/* Retail participation detail */}
      {data.hasRetailData && data.retailScore !== null && (
        <div className="mb-3 bg-stone-50 rounded-xl px-3 py-2.5 space-y-1.5">
          <p className="text-xs font-semibold text-stone-600 uppercase tracking-wider">
            Partisipasi Retail
          </p>
          <div className="flex justify-between items-center text-xs text-stone-500">
            <span>Arah</span>
            <span className={`font-semibold ${data.retailDirection === 1 ? 'text-green-600' : data.retailDirection === -1 ? 'text-red-600' : 'text-stone-500'}`}>
              {directionLabel}
            </span>
          </div>
          {data.domesticNetBn !== null && (
            <div className="flex justify-between items-center text-xs text-stone-500">
              <span>Net domestik</span>
              <span className={`font-semibold tabular-nums ${data.domesticNetBn >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {data.domesticNetBn >= 0 ? '+' : ''}{data.domesticNetBn.toFixed(0)} miliar
              </span>
            </div>
          )}
          {data.retailRatio !== null && (
            <div className="flex justify-between items-center text-xs text-stone-500">
              <span>Volume vs rata-rata</span>
              <span className="font-semibold text-stone-700">{data.retailRatio.toFixed(2)}×</span>
            </div>
          )}
          <div className="flex justify-between items-center text-xs text-stone-500">
            <span>Skor partisipasi</span>
            <span className={`font-bold ${zoneColors(data.retailScore).text}`}>
              {Math.round(data.retailScore)} / 100
            </span>
          </div>
        </div>
      )}

      {/* Raw vs smoothed */}
      {data.rawScore !== null && data.score !== null && Math.abs(data.rawScore - data.score) > 0.5 && (
        <p className="text-center text-xs text-stone-400 mb-2">
          Raw {data.rawScore.toFixed(1)} · Smoothed {data.score.toFixed(1)}
        </p>
      )}

      {/* Footer */}
      <div className="flex justify-between items-center pt-2 border-t border-stone-100">
        <span className="text-xs text-stone-400">
          {data.daysOfRetailData > 0
            ? `${data.daysOfRetailData} hari data domestik`
            : 'Belum ada data domestik'}
        </span>
        <span className="text-xs text-stone-400">Updated {wib} WIB</span>
      </div>
    </div>
  );
}
