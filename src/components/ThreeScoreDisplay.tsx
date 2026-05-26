'use client';

import { useEffect, useState } from 'react';
import { zoneColors } from '@/lib/zoneColors';
import type { SentimentScoresResponse } from '@/app/api/sentiment-scores/route';

// ── Mini gauge arc (compact — fits in a small card) ───────────────────────────

function MiniGauge({
  score,
  size = 'md',
}: {
  score: number | null;
  size?: 'sm' | 'md' | 'lg';
}) {
  const s = score ?? 50;
  const { hex } = zoneColors(score);
  const cx = 60, cy = 60, r = 46;
  const arcLen = Math.PI * r;
  const arcPath = `M 14 ${cy} A ${r} ${r} 0 0 1 106 ${cy}`;
  const needleDeg = -90 + (s / 100) * 180;

  const dimClass = size === 'lg' ? 'w-40' : size === 'md' ? 'w-28' : 'w-20';

  return (
    <svg viewBox="0 0 120 74" className={dimClass} aria-hidden="true">
      <defs>
        <linearGradient id="mgArcGrad" gradientUnits="userSpaceOnUse" x1="14" y1="0" x2="106" y2="0">
          <stop offset="0%"   stopColor="#ef4444" />
          <stop offset="25%"  stopColor="#f97316" />
          <stop offset="50%"  stopColor="#eab308" />
          <stop offset="75%"  stopColor="#84cc16" />
          <stop offset="100%" stopColor="#10b981" />
        </linearGradient>
      </defs>
      <path d={arcPath} fill="none" stroke="#e7e5e4" strokeWidth="9" strokeLinecap="round" />
      <path
        d={arcPath} fill="none" stroke="url(#mgArcGrad)" strokeWidth="9" strokeLinecap="round"
        strokeDasharray={`${(s / 100) * arcLen} ${arcLen}`}
      />
      <g transform={`rotate(${needleDeg}, ${cx}, ${cy})`}>
        <line x1={cx} y1={cy} x2={cx} y2={cy - 38} stroke="#292524" strokeWidth="1.8" strokeLinecap="round" />
        <circle cx={cx} cy={cy - 38} r={5} fill={hex} />
      </g>
      <circle cx={cx} cy={cy} r={4} fill="#292524" />
    </svg>
  );
}

// ── Score badge ────────────────────────────────────────────────────────────────

function ScoreBadge({ score, label }: { score: number | null; label: string }) {
  const { text, bg } = zoneColors(score);
  return (
    <div className="text-center">
      <p className={`text-4xl font-bold tabular-nums leading-none ${text}`}>
        {score != null ? Math.round(score) : '—'}
      </p>
      <span className={`inline-block mt-2 px-3 py-0.5 rounded-full text-xs font-bold text-white ${bg}`}>
        {label}
      </span>
    </div>
  );
}

// ── Individual score panel ─────────────────────────────────────────────────────

function ScorePanel({
  title,
  subtitle,
  score,
  label,
  size = 'md',
  badge,
  footnote,
}: {
  title:    string;
  subtitle: string;
  score:    number | null;
  label:    string;
  size?:    'sm' | 'md' | 'lg';
  badge?:   React.ReactNode;
  footnote?: string;
}) {
  return (
    <div className="bg-white border border-stone-200 rounded-2xl p-4 shadow-sm flex flex-col items-center gap-2">
      <div className="text-center w-full">
        <div className="flex items-center justify-center gap-1.5 flex-wrap">
          <h3 className={`font-bold text-stone-900 ${size === 'lg' ? 'text-base' : 'text-sm'}`}>
            {title}
          </h3>
          {badge}
        </div>
        <p className="text-xs text-stone-400 mt-0.5">{subtitle}</p>
      </div>
      <MiniGauge score={score} size={size} />
      <ScoreBadge score={score} label={label} />
      {footnote && (
        <p className="text-xs text-stone-400 text-center leading-relaxed">{footnote}</p>
      )}
    </div>
  );
}

// ── Divergence callout ─────────────────────────────────────────────────────────

function DivergenceCallout({
  signal,
  magnitude,
  message,
}: {
  signal:    string;
  magnitude: number;
  message:   string;
}) {
  const isRetailEuforia = signal === 'ritel_euforia';
  const icon   = isRetailEuforia ? '⚡' : '🔭';
  const title  = isRetailEuforia
    ? `Ritel euforia, asing mengurangi posisi (${magnitude.toFixed(0)}pt gap)`
    : `Asing lebih optimis dari ritel (${magnitude.toFixed(0)}pt gap)`;

  return (
    <div className="bg-amber-50 border border-amber-200 rounded-2xl px-4 py-3 flex gap-3 items-start">
      <span className="text-xl flex-shrink-0 mt-0.5">{icon}</span>
      <div>
        <p className="text-sm font-semibold text-amber-900">{title}</p>
        <p className="text-xs text-amber-700 mt-0.5 leading-relaxed">{message}</p>
      </div>
    </div>
  );
}

// ── Overall summary bar ────────────────────────────────────────────────────────

function SummaryBar({
  overall,
  foreign,
  domestic,
}: {
  overall:  { score: number | null; label: string };
  foreign:  { score: number | null; label: string };
  domestic: { score: number | null; label: string; hasDomesticData: boolean };
}) {
  const { text: ovText } = zoneColors(overall.score);
  const { text: fgText } = zoneColors(foreign.score);
  const { text: domText } = zoneColors(domestic.score);

  return (
    <div className="bg-white border border-stone-200 rounded-2xl px-5 py-3 shadow-sm">
      <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm">
        <div className="flex items-center gap-1.5">
          <span className="text-stone-500 font-medium">Overall</span>
          <span className={`font-bold tabular-nums ${ovText}`}>
            {overall.score != null ? Math.round(overall.score) : '—'}
          </span>
          <span className="text-stone-400 text-xs">({overall.label})</span>
        </div>
        <span className="text-stone-200 hidden sm:block">|</span>
        <div className="flex items-center gap-1.5">
          <span className="text-stone-500 font-medium">Asing</span>
          <span className={`font-bold tabular-nums ${fgText}`}>
            {foreign.score != null ? Math.round(foreign.score) : '—'}
          </span>
          <span className="text-stone-400 text-xs">({foreign.label})</span>
        </div>
        <span className="text-stone-200 hidden sm:block">|</span>
        <div className="flex items-center gap-1.5">
          <span className="text-stone-500 font-medium">Ritel</span>
          {domestic.hasDomesticData ? (
            <>
              <span className={`font-bold tabular-nums ${domText}`}>
                {domestic.score != null ? Math.round(domestic.score) : '—'}
              </span>
              <span className="text-stone-400 text-xs">({domestic.label})</span>
            </>
          ) : (
            <span className="text-stone-400 text-xs italic">belum ada data</span>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function ThreeScoreDisplay() {
  const [data, setData]       = useState<SentimentScoresResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/sentiment-scores')
      .then(r => r.json())
      .then((d: SentimentScoresResponse) => {
        setData(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-10 bg-stone-100 rounded-2xl animate-pulse" />
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[0, 1, 2].map(i => (
            <div key={i} className="h-52 bg-stone-100 rounded-2xl animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (!data) return null;

  const { overall, foreign, domestic, divergence } = data;

  // Domestic participation mode footnote
  const domFootnote = !domestic.hasDomesticData
    ? 'Masukkan data domestik harian untuk mulai melacak sentimen ritel.'
    : domestic.daysOfData < 5
    ? `Data terbatas — ${domestic.daysOfData} hari dikumpulkan. Sinyal akan stabil setelah 20+ hari.`
    : domestic.participationMode === 'market_share'
    ? `Partisipasi: ${domestic.participationRatio?.toFixed(2) ?? '—'}× market share rata-rata`
    : `Partisipasi: ${domestic.participationRatio?.toFixed(2) ?? '—'}× volume rata-rata`;

  // Overall footnote — explain the blend
  const ovFootnote = overall.hasDomesticData
    ? `${Math.round(overall.foreignWeight * 100)}% Asing + ${Math.round(overall.domesticWeight * 100)}% Ritel`
    : 'Fallback ke Sentimen Asing (data ritel belum tersedia)';

  return (
    <div className="space-y-3">
      {/* Summary bar — quick glance */}
      <SummaryBar overall={overall} foreign={foreign} domestic={domestic} />

      {/* Divergence callout (only when gap is significant) */}
      {divergence && (
        <DivergenceCallout
          signal={divergence.signal}
          magnitude={divergence.magnitude}
          message={divergence.message}
        />
      )}

      {/* Three score panels */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Overall — center column, slightly larger */}
        <ScorePanel
          title="Overall"
          subtitle={ovFootnote}
          score={overall.score}
          label={overall.label}
          size="lg"
        />

        {/* Foreign Sentiment */}
        <ScorePanel
          title="Sentimen Asing"
          subtitle="Investor institusional asing"
          score={foreign.score}
          label={foreign.label}
          size="md"
        />

        {/* Domestic Sentiment */}
        <ScorePanel
          title="Sentimen Ritel"
          subtitle="Investor domestik / ritel"
          score={domestic.hasDomesticData ? domestic.score : null}
          label={domestic.hasDomesticData ? domestic.label : 'Belum Ada Data'}
          size="md"
          badge={
            domestic.hasDomesticData && domestic.daysOfData < 20
              ? (
                <span className="text-xs bg-amber-50 text-amber-600 border border-amber-200 rounded-full px-1.5 py-0.5 leading-none">
                  {domestic.daysOfData}h
                </span>
              )
              : undefined
          }
          footnote={domFootnote}
        />
      </div>

      {/* Data availability note */}
      <p className="text-xs text-stone-400 text-center leading-relaxed">
        Ini adalah sinyal sentimen pasar, bukan rekomendasi investasi.{' '}
        Sentimen Asing valid sejak Agt 2025 (182 hari data).{' '}
        Sentimen Ritel mulai dikumpulkan {domestic.date ?? 'hari ini'}.
      </p>
    </div>
  );
}
