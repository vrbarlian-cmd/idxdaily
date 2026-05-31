'use client';

import { useState, useRef, useEffect } from 'react';
import type { FearGreedData, ComponentResult } from '@/lib/fearGreed';
import { zoneColors } from '@/lib/zoneColors';

// ── SVG gauge ─────────────────────────────────────────────────────────────────

function GaugeSVG({ score, isNull }: { score: number; isNull: boolean }) {
  const cx = 150, cy = 150, r = 120;
  const needleLen = 105, tipR = 11, pivotR = 7;
  const arcLen    = Math.PI * r;
  const arcPath   = `M 30 ${cy} A ${r} ${r} 0 0 1 270 ${cy}`;
  const needleDeg = -90 + (score / 100) * 180;

  const { hex } = zoneColors(isNull ? null : score);

  const tipText = isNull ? '—' : String(Math.round(score));
  const tipFs   = tipText.length > 2 ? 8 : 10;

  return (
    <svg viewBox="0 0 300 170" className="w-full" aria-hidden="true">
      <defs>
        <linearGradient id="arcGrad" gradientUnits="userSpaceOnUse" x1="30" y1="0" x2="270" y2="0">
          <stop offset="0%"   stopColor="#b91c1c" />
          <stop offset="25%"  stopColor="#d97706" />
          <stop offset="50%"  stopColor="#6b7280" />
          <stop offset="75%"  stopColor="#059669" />
          <stop offset="100%" stopColor="#047857" />
        </linearGradient>
      </defs>

      {/* Track */}
      <path d={arcPath} fill="none" stroke="#f0ede8" strokeWidth="14" strokeLinecap="round" />

      {/* Filled arc */}
      <path
        d={arcPath}
        fill="none"
        stroke="url(#arcGrad)"
        strokeWidth="14"
        strokeLinecap="round"
        strokeDasharray={`${(score / 100) * arcLen} ${arcLen}`}
      />

      {/* Needle */}
      <g transform={`rotate(${needleDeg}, ${cx}, ${cy})`}>
        <line
          x1={cx} y1={cy} x2={cx} y2={cy - needleLen}
          stroke="#1e293b" strokeWidth="2" strokeLinecap="round"
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

      {/* Pivot dot */}
      <circle cx={cx} cy={cy} r={pivotR} fill="#1e293b" />

      {/* Zone labels */}
      <text x="30"  y="168" textAnchor="start" fontSize="9" fill="#d1cdc7"
        fontFamily="ui-sans-serif, system-ui, sans-serif">
        Extreme Fear
      </text>
      <text x="270" y="168" textAnchor="end" fontSize="9" fill="#d1cdc7"
        fontFamily="ui-sans-serif, system-ui, sans-serif">
        Extreme Greed
      </text>
    </svg>
  );
}

// ── Component popover ─────────────────────────────────────────────────────────

function ComponentPopover({
  components,
  activeCount,
  onClose,
}: {
  components:  ComponentResult[];
  activeCount: number;
  onClose:     () => void;
}) {
  return (
    <div className="absolute top-8 right-0 z-50 w-72 bg-white border border-[#e5e2db] rounded-2xl shadow-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-[#6b7280] uppercase tracking-wider">
          Components · {activeCount}/6 active
        </p>
        <button
          onClick={onClose}
          className="text-[#9ca3af] hover:text-[#374151] text-xs leading-none p-1"
        >
          ✕
        </button>
      </div>

      <div className="space-y-2.5">
        {components.map(c => {
          const { text } = zoneColors(c.score);
          const effPct = Math.round(c.weight * 100);
          return (
            <div key={c.id} className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <p className={`text-xs ${c.status === 'unavailable' ? 'text-[#9ca3af]' : 'text-[#374151]'}`}>
                  {c.label}
                  <span className="text-[#d1cdc7] ml-1">{effPct}%</span>
                  {c.status === 'stale' && <span className="text-amber-400 ml-1">⚠</span>}
                </p>
                {c.rawLabel && c.status !== 'unavailable' && (
                  <p className="text-xs text-[#9ca3af] truncate mt-0.5">{c.rawLabel}</p>
                )}
              </div>
              <span className={`text-xs font-bold flex-shrink-0 ${c.score != null ? text : 'text-[#d1cdc7]'}`}>
                {c.score != null ? c.score.toFixed(0) : '—'}
              </span>
            </div>
          );
        })}
      </div>

      <p className="text-xs text-[#9ca3af] mt-3 pt-2 border-t border-[#f0ede8]">
        Weights renormalized over active components.
      </p>
    </div>
  );
}

// ── Main gauge panel (borderless — outer card provided by page.tsx) ───────────

export default function FearGreedGauge({
  data,
  indexTitle,
  indexSubtitle,
}: {
  data:           FearGreedData;
  indexTitle?:    string;
  indexSubtitle?: string;
}) {
  const [showPopover, setShowPopover] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!showPopover) return;
    const handler = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setShowPopover(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showPopover]);

  const displayScore = data.score ?? 50;
  const { text, hex } = zoneColors(data.score);

  const wib = new Date().toLocaleTimeString('id-ID', {
    hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Jakarta',
  });

  return (
    <div className="p-5">
      {/* Panel header */}
      <div className="flex items-start justify-between mb-1">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-[#9ca3af] mb-0.5">
            Market Sentiment
          </p>
          <h2 className="text-sm font-bold text-[#0f172a]">
            {indexTitle ?? 'IDX Fear & Greed Index'}
          </h2>
        </div>

        {/* "?" button */}
        <div ref={popoverRef} className="relative flex-shrink-0">
          <button
            onClick={() => setShowPopover(v => !v)}
            className={`w-6 h-6 rounded-full border text-xs flex items-center justify-center transition-colors ${
              showPopover
                ? 'border-blue-400 text-blue-600 bg-blue-50'
                : 'border-[#e5e2db] text-[#9ca3af] hover:border-[#374151] hover:text-[#374151]'
            }`}
            title="View component breakdown"
          >
            ?
          </button>
          {showPopover && (
            <ComponentPopover
              components={data.components}
              activeCount={data.activeComponents}
              onClose={() => setShowPopover(false)}
            />
          )}
        </div>
      </div>

      {/* Gauge SVG — capped width so it doesn't balloon on mobile */}
      <div className="max-w-[260px] mx-auto">
        <GaugeSVG score={displayScore} isNull={data.score == null} />
      </div>

      {/* Score + label */}
      <div className="text-center -mt-1 mb-3">
        <p className={`text-4xl font-black leading-none tabular-nums ${text}`}>
          {data.score != null ? Math.round(data.score) : '—'}
        </p>
        <p className={`mt-1.5 text-[11px] font-semibold uppercase tracking-widest ${text}`}>
          {data.label}
        </p>
      </div>

      {/* Sentiment bars */}
      {data.articleCount > 0 && (
        <div className="mb-4 px-1">
          <div className="flex h-1.5 rounded-full overflow-hidden gap-px">
            <div
              className="bg-emerald-500 transition-all rounded-l-full"
              style={{ width: `${data.bullishPct}%` }}
              title={`Bullish ${data.bullishPct}%`}
            />
            <div
              className="bg-[#e5e2db] transition-all"
              style={{ width: `${data.neutralPct}%` }}
              title={`Neutral ${data.neutralPct}%`}
            />
            <div
              className="bg-red-400 transition-all rounded-r-full"
              style={{ width: `${data.bearishPct}%` }}
              title={`Bearish ${data.bearishPct}%`}
            />
          </div>
          <div className="flex justify-between text-[10px] text-[#9ca3af] mt-1.5 px-0.5">
            <span className="text-emerald-600 font-semibold">{data.bullishPct}% Bull</span>
            <span>{data.neutralPct}% Netral</span>
            <span className="text-red-500 font-semibold">{data.bearishPct}% Bear</span>
          </div>
        </div>
      )}

      {/* Raw vs smoothed */}
      {data.rawScore != null && data.score != null && Math.abs(data.rawScore - data.score) > 0.5 && (
        <p className="text-center text-[10px] text-[#9ca3af] mb-3">
          Raw {data.rawScore.toFixed(1)} · Smoothed {data.score.toFixed(1)}
        </p>
      )}

      {/* Footer */}
      <div className="flex justify-between items-center pt-2 border-t border-[#f0ede8]">
        <span className="text-[10px] text-[#9ca3af]">idxdaily.id</span>
        <span className="text-[10px] text-[#9ca3af]">Updated {wib} WIB</span>
      </div>
    </div>
  );
}
