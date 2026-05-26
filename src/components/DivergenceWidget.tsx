'use client';

/**
 * DivergenceWidget — client component
 *
 * Fetches /api/divergence and shows today's foreign vs domestic flow
 * divergence signal. Hidden when no domestic data has been entered yet,
 * or on weekends.
 *
 * This is an informational sentiment indicator, NOT investment advice.
 */

import { useEffect, useState } from 'react';

interface DivergenceData {
  date: string;
  has_domestic_data: boolean;
  foreign_net_bn: number | null;
  domestic_net_bn: number | null;
  signal: 'optimisme_retail' | 'ketakutan_retail' | 'sejalan';
  label: string;
  description: string;
  notable: boolean;
}

function fmt(n: number | null): string {
  if (n === null) return '—';
  const abs = Math.abs(n).toLocaleString('id-ID', { maximumFractionDigits: 0 });
  return (n >= 0 ? '+' : '−') + abs;
}

export default function DivergenceWidget() {
  const [data, setData] = useState<DivergenceData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/divergence')
      .then(r => r.json())
      .then((d: DivergenceData) => setData(d))
      .catch(() => {/* silently hide on error */})
      .finally(() => setLoading(false));
  }, []);

  // Don't render until loaded; hide if no domestic data
  if (loading || !data || !data.has_domestic_data) return null;

  // ── Colour scheme based on signal ──────────────────────────────────────────
  const scheme = data.notable
    ? data.signal === 'optimisme_retail'
      ? {
          bg: 'bg-amber-50',
          border: 'border-amber-300',
          header: 'text-amber-800',
          badge: 'bg-amber-100 text-amber-700',
          icon: '⚡',
        }
      : {
          bg: 'bg-blue-50',
          border: 'border-blue-300',
          header: 'text-blue-800',
          badge: 'bg-blue-100 text-blue-700',
          icon: '📡',
        }
    : {
        bg: 'bg-stone-50',
        border: 'border-stone-200',
        header: 'text-stone-700',
        badge: 'bg-stone-100 text-stone-500',
        icon: '↔',
      };

  return (
    <div className={`rounded-2xl border ${scheme.border} ${scheme.bg} p-5 space-y-3`}>
      {/* Header row */}
      <div className="flex items-center justify-between">
        <span className={`text-xs font-semibold uppercase tracking-widest ${scheme.header}`}>
          {scheme.icon}&nbsp; Sinyal Sentimen Kontrarian
        </span>
        <span className={`text-xs rounded-full px-2.5 py-0.5 font-medium ${scheme.badge}`}>
          {data.label}
        </span>
      </div>

      {/* Flow figures */}
      <div className="grid grid-cols-2 gap-3">
        <FlowCard
          title="Asing (Net)"
          value={data.foreign_net_bn}
          positiveLabel="Net Buy"
          negativeLabel="Net Jual"
        />
        <FlowCard
          title="Domestik (Net)"
          value={data.domestic_net_bn}
          positiveLabel="Net Beli"
          negativeLabel="Net Jual"
        />
      </div>

      {/* Description */}
      <p className="text-xs text-stone-500 leading-relaxed">
        {data.description}
      </p>

      {/* Disclaimer */}
      <p className="text-[10px] text-stone-400 italic">
        Bukan rekomendasi beli/jual. Hanya gambaran sentimen kontrarian berdasarkan data flow publik.
      </p>
    </div>
  );
}

function FlowCard({
  title,
  value,
  positiveLabel,
  negativeLabel,
}: {
  title: string;
  value: number | null;
  positiveLabel: string;
  negativeLabel: string;
}) {
  const isPositive = value !== null && value >= 0;
  const color = value === null
    ? 'text-stone-400'
    : isPositive
    ? 'text-emerald-600'
    : 'text-red-500';

  return (
    <div className="bg-white rounded-xl border border-stone-100 px-4 py-3 space-y-1">
      <p className="text-xs text-stone-400 font-medium">{title}</p>
      <p className={`text-lg font-bold font-mono ${color}`}>
        {fmt(value)}
      </p>
      {value !== null && (
        <p className={`text-xs font-medium ${color}`}>
          {isPositive ? positiveLabel : negativeLabel}
        </p>
      )}
      <p className="text-[10px] text-stone-400">IDR Miliar</p>
    </div>
  );
}
