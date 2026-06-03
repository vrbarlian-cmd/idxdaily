'use client';

import { useState, useRef, useEffect } from 'react';
import type { FearGreedData, ComponentResult } from '@/lib/fearGreed';
import { zoneColors } from '@/lib/zoneColors';

// ── SVG gauge ─────────────────────────────────────────────────────────────────

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
        <linearGradient id="arcGrad" gradientUnits="userSpaceOnUse" x1="30" y1="0" x2="270" y2="0">
          <stop offset="0%"   stopColor="#ef4444" />
          <stop offset="25%"  stopColor="#f97316" />
          <stop offset="50%"  stopColor="#eab308" />
          <stop offset="75%"  stopColor="#84cc16" />
          <stop offset="100%" stopColor="#10b981" />
        </linearGradient>
        <filter id="glowNeedle">
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
        stroke="url(#arcGrad)"
        strokeWidth="20"
        strokeLinecap="round"
        strokeDasharray={`${((score / 100) * arcLen).toFixed(3)} ${arcLen.toFixed(3)}`}
      />

      {/* Needle + tip circle */}
      <g transform={`rotate(${needleDeg}, ${cx}, ${cy})`} filter="url(#glowNeedle)">
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

      {/* Pivot dot */}
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
    <div className="absolute top-8 right-0 z-50 w-72 bg-white border border-stone-200 rounded-2xl shadow-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-stone-600 uppercase tracking-wider">
          Components · {activeCount}/6 active
        </p>
        <button
          onClick={onClose}
          className="text-stone-400 hover:text-stone-600 text-xs leading-none p-1"
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
                <p className={`text-xs ${c.status === 'unavailable' ? 'text-stone-400' : 'text-stone-700'}`}>
                  {c.label}
                  <span className="text-stone-300 ml-1">{effPct}%</span>
                  {c.status === 'stale' && <span className="text-amber-400 ml-1">⚠</span>}
                </p>
                {c.rawLabel && c.status !== 'unavailable' && (
                  <p className="text-xs text-stone-400 truncate mt-0.5">{c.rawLabel}</p>
                )}
              </div>
              <span className={`text-xs font-bold flex-shrink-0 ${c.score != null ? text : 'text-stone-300'}`}>
                {c.score != null ? c.score.toFixed(0) : '—'}
              </span>
            </div>
          );
        })}
      </div>

      <p className="text-xs text-stone-400 mt-3 pt-2 border-t border-stone-100">
        Weights renormalized over active components.
      </p>
    </div>
  );
}

// ── Main gauge card ───────────────────────────────────────────────────────────

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
  const [wib, setWib] = useState('');
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

  // Set WIB time on the client only — new Date() during SSR produces a
  // different clock value than during hydration, causing a hydration mismatch.
  useEffect(() => {
    setWib(new Date().toLocaleTimeString('id-ID', {
      hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Jakarta',
    }));
  }, []);

  const displayScore = data.score ?? 50;
  const { text, bg, hex } = zoneColors(data.score);

  return (
    <div className="bg-white border border-stone-200 rounded-2xl p-5 shadow-sm">
      {/* Card header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-base font-bold text-stone-900">
            {indexTitle ?? 'IDX Fear & Greed Index'}
          </h2>
          <p className="text-xs text-stone-500 mt-0.5">
            {indexSubtitle ?? 'Multifactor IDX market sentiment'}
          </p>
        </div>

        {/* "?" button */}
        <div ref={popoverRef} className="relative flex-shrink-0">
          <button
            onClick={() => setShowPopover(v => !v)}
            className={`w-6 h-6 rounded-full border text-xs flex items-center justify-center transition-colors ${
              showPopover
                ? 'border-brand-400 text-brand-600 bg-brand-50'
                : 'border-stone-200 text-stone-400 hover:border-stone-400 hover:text-stone-600'
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

      <div className="border-t border-stone-100 my-3" />

      {/* Gauge SVG */}
      <GaugeSVG score={displayScore} isNull={data.score == null} />

      {/* Score number with zone glow */}
      <div className="text-center -mt-1 mb-3 relative">
        {/* Soft glow blob behind the number */}
        {data.score != null && (
          <div
            className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-24 h-24 rounded-full blur-3xl pointer-events-none"
            style={{ backgroundColor: hex, opacity: 0.18 }}
          />
        )}
        <p
          className={`text-5xl font-bold leading-none tabular-nums relative ${text}`}
          style={data.score != null ? {
            filter: `drop-shadow(0 0 6px ${hex}55)`,
          } : {}}
        >
          {data.score != null ? Number(data.score).toFixed(1) : '—'}
        </p>
        <span className={`inline-block mt-2.5 px-4 py-1 rounded-full text-xs font-bold text-white ${bg}`}>
          {data.label}
        </span>
      </div>

      {/* Raw vs smoothed */}
      {data.rawScore != null && data.score != null && Math.abs(data.rawScore - data.score) > 0.5 && (
        <p className="text-center text-xs text-stone-400 mb-2">
          Raw {data.rawScore.toFixed(1)} · Smoothed {data.score.toFixed(1)}
        </p>
      )}

      {/* Footer */}
      <div className="flex justify-between items-center pt-2 border-t border-stone-100">
        <span className="text-xs text-stone-400">idxdaily.id</span>
        <span className="text-xs text-stone-400">Updated {wib} WIB</span>
      </div>
    </div>
  );
}
