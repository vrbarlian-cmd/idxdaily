import { Clock } from 'lucide-react';
import type { HistoricalValues, HistoricalEntry } from '@/lib/fearGreed';

// ── Zone color + label ──────────────────────────────────────────────────────
// Single source: the SAME hex drives both the badge circle and the label text,
// and the label words use the same thresholds — so they can never disagree.
function zone(score: number | null): { color: string; label: string } {
  if (score == null) return { color: '#A8A29E', label: '—'             };
  if (score >= 75)   return { color: '#059669', label: 'Extreme Greed' };  // dark green
  if (score >= 60)   return { color: '#10B981', label: 'Greed'         };  // green
  if (score >= 45)   return { color: '#F59E0B', label: 'Neutral'       };  // yellow
  if (score >= 30)   return { color: '#F97316', label: 'Fear'          };  // orange
  return                    { color: '#E24B4A', label: 'Extreme Fear'  };  // red
}

// ── Score badge ───────────────────────────────────────────────────────────────

function ScoreBadge({ value }: { value: number | null }) {
  const { color } = zone(value);
  return (
    <div
      className="w-11 h-11 rounded-full flex items-center justify-center flex-shrink-0"
      style={{ backgroundColor: color }}
    >
      <span className="text-white text-xs font-bold leading-none">
        {value != null ? Math.round(value) : '—'}
      </span>
    </div>
  );
}

// ── Single row ────────────────────────────────────────────────────────────────

function HistRow({ period, entry }: { period: string; entry: HistoricalEntry }) {
  // Badge background and label text use the identical zone() color.
  const { color, label } = zone(entry.value);

  return (
    <div className="flex items-center justify-between py-3.5">
      <div>
        <p className="text-sm font-medium text-stone-700">{period}</p>
        <p className="text-sm" style={{ color: entry.value != null ? color : '#A8A29E' }}>
          {entry.value != null ? label : '—'}
        </p>
      </div>
      <ScoreBadge value={entry.value} />
    </div>
  );
}

// ── Card ──────────────────────────────────────────────────────────────────────

export default function FearGreedHistorical({ data }: { data: HistoricalValues }) {
  const rows: { period: string; entry: HistoricalEntry }[] = [
    { period: 'Now',        entry: data.now       },
    { period: 'Yesterday',  entry: data.yesterday },
    { period: 'Last week',  entry: data.lastWeek  },
    { period: 'Last month', entry: data.lastMonth },
  ];

  return (
    <div className="bg-white border border-stone-200 rounded-xl p-5">
      <div className="flex items-center gap-2">
        <Clock className="w-4 h-4 text-stone-400 flex-shrink-0" />
        <h2 className="text-base font-semibold text-stone-900">Historical Values</h2>
      </div>

      <div className="border-t border-stone-100 mt-3">
        {rows.map(({ period, entry }, i) => (
          <div key={period}>
            <HistRow period={period} entry={entry} />
            {i < rows.length - 1 && <div className="border-t border-stone-100" />}
          </div>
        ))}
      </div>
    </div>
  );
}
