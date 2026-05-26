'use client';

import { useState } from 'react';
import { BarChart3, ChevronDown, AlertCircle } from 'lucide-react';
import type { ComponentResult } from '@/lib/fearGreed';
import { zoneColors } from '@/lib/zoneColors';

// ── Component row ─────────────────────────────────────────────────────────────

interface RowProps {
  c:               ComponentResult;
  effectiveWeight: number;   // 0–1, after redistribution
}

function ComponentRow({ c, effectiveWeight }: RowProps) {
  const { text }       = zoneColors(c.score);
  const nominalPct     = Math.round(c.weight * 100);
  const effectivePct   = Math.round(effectiveWeight * 100);
  const isUnavailable  = c.status === 'unavailable';
  const weightChanged  = !isUnavailable && effectivePct !== nominalPct;

  function barClass(score: number): string {
    if (score < 25) return 'bg-red-500';
    if (score < 45) return 'bg-orange-500';
    if (score < 55) return 'bg-yellow-400';
    if (score < 75) return 'bg-lime-500';
    return 'bg-green-600';
  }

  return (
    <div className={isUnavailable ? 'opacity-55' : ''}>

      {/* Label + weight + score */}
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5 min-w-0 flex-1">
          <span className={`text-sm truncate ${isUnavailable ? 'text-stone-400' : 'text-stone-700'}`}>
            {c.label}
          </span>

          {/* Nominal weight (always shown) */}
          <span className="text-xs text-stone-300 flex-shrink-0">{nominalPct}%</span>

          {/* Effective weight (only shown when redistribution changed it) */}
          {weightChanged && (
            <span
              className="text-xs text-emerald-600 font-medium flex-shrink-0"
              title="Bobot efektif setelah komponen lain dinonaktifkan"
            >
              →{effectivePct}%
            </span>
          )}

          {/* Stale warning */}
          {c.status === 'stale' && (
            <span className="text-amber-400 text-xs flex-shrink-0" title={c.note ?? undefined}>
              ⚠
            </span>
          )}
        </div>

        {/* Score */}
        {c.score != null ? (
          <span className={`text-sm font-semibold flex-shrink-0 ml-2 ${text}`}>
            {c.score.toFixed(0)}
          </span>
        ) : (
          <span className="text-xs text-stone-300 flex-shrink-0 ml-2">N/A</span>
        )}
      </div>

      {/* Progress bar */}
      <div className="h-1.5 bg-stone-100 rounded-full overflow-hidden">
        {c.score != null ? (
          <div
            className={`h-1.5 rounded-full transition-all ${barClass(c.score)}`}
            style={{ width: `${c.score}%` }}
          />
        ) : (
          /* Striped/dashed bar to signal unavailable */
          <div className="h-1.5 w-full rounded-full bg-stone-200/60" style={{
            backgroundImage: 'repeating-linear-gradient(90deg, transparent 0px, transparent 4px, #e7e5e4 4px, #e7e5e4 8px)',
          }} />
        )}
      </div>

      {/* Sub-text */}
      {c.rawLabel && !isUnavailable && (
        <p className="text-xs text-stone-400 mt-0.5">{c.rawLabel}</p>
      )}
      {isUnavailable && c.note && (
        <p className="text-xs text-stone-400 mt-0.5 flex items-start gap-1">
          <AlertCircle className="w-3 h-3 flex-shrink-0 mt-0.5 text-stone-300" />
          <span>{c.note}</span>
        </p>
      )}
      {c.status === 'stale' && c.note && (
        <p className="text-xs text-amber-600 mt-0.5">{c.note}</p>
      )}
    </div>
  );
}

// ── Collapsible panel ─────────────────────────────────────────────────────────

interface Props {
  components:  ComponentResult[];
  activeCount: number;
}

export default function FearGreedComponents({ components, activeCount }: Props) {
  const [open, setOpen] = useState(false);
  const total = components.length;

  // Compute effective weights: active components share the full 1.0 pool
  const activeComponents = components.filter(c => c.score !== null);
  const totalActiveWeight = activeComponents.reduce((s, c) => s + c.weight, 0);

  function effectiveWeight(c: ComponentResult): number {
    if (c.score === null) return 0;
    return totalActiveWeight > 0 ? c.weight / totalActiveWeight : c.weight;
  }

  return (
    <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">

      {/* Toggle header */}
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-stone-50 transition-colors text-left"
      >
        <div className="flex items-center gap-2.5">
          <BarChart3 className="w-4 h-4 text-stone-400 flex-shrink-0" />
          <span className="text-sm font-medium text-stone-700">Komponen indeks</span>
          <span className="text-xs text-stone-500 bg-stone-100 px-2 py-0.5 rounded-full">
            {activeCount}/{total} aktif
          </span>
          {activeCount < total && (
            <span className="text-xs text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full">
              {total - activeCount} tidak tersedia
            </span>
          )}
        </div>
        <ChevronDown
          className={`w-4 h-4 text-stone-400 transition-transform flex-shrink-0 ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Expanded panel */}
      {open && (
        <div className="px-5 pb-5 border-t border-stone-100">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-5 mt-4">
            {components.map(c => (
              <ComponentRow key={c.id} c={c} effectiveWeight={effectiveWeight(c)} />
            ))}
          </div>

          {/* Footer explanation */}
          <div className="mt-4 pt-3 border-t border-stone-100 space-y-2">
            <p className="text-xs text-stone-400">
              Indeks dihitung dari{' '}
              <span className="font-medium text-stone-600">{activeCount}/{total}</span>{' '}
              komponen aktif. Bobot komponen yang tidak tersedia didistribusikan ulang secara proporsional ke komponen aktif.
              {activeCount < total && (
                <span className="ml-1 text-amber-600">
                  (Bobot efektif ditampilkan dengan tanda →)
                </span>
              )}
            </p>

            <details>
              <summary className="text-xs text-stone-400 hover:text-stone-600 cursor-pointer select-none">
                Cara perhitungan?
              </summary>
              <div className="mt-2 text-xs text-stone-500 bg-stone-50 rounded-lg p-3 border border-stone-100 space-y-1.5">
                <p className="font-medium text-stone-600">Metodologi persentil:</p>
                <p>
                  Setiap komponen diukur sebagai{' '}
                  <strong>peringkat persentil vs 90–250 hari historis</strong>,
                  bukan nilai absolut. Skor 20 = nilai saat ini lebih rendah dari 80% riwayat (zona Fear).
                </p>
                <p>
                  <strong>EMA smoothing (α=0.7):</strong> skor harian dihaluskan dengan exponential moving average
                  untuk mengurangi fluktuasi jangka pendek.
                </p>
              </div>
            </details>
          </div>
        </div>
      )}
    </div>
  );
}
