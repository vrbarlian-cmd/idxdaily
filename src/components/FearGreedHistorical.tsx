import { Clock } from 'lucide-react';
import type { HistoricalValues, HistoricalEntry } from '@/lib/fearGreed';
import { zoneColors } from '@/lib/zoneColors';

// ── Score badge ───────────────────────────────────────────────────────────────

function ScoreBadge({ value }: { value: number | null }) {
  const { bg } = zoneColors(value);
  return (
    <div
      className={`w-11 h-11 rounded-full flex items-center justify-center flex-shrink-0 ${bg}`}
    >
      <span className="text-white text-xs font-bold leading-none">
        {value != null ? Math.round(value) : '—'}
      </span>
    </div>
  );
}

// ── Single row ────────────────────────────────────────────────────────────────

function HistRow({ period, entry }: { period: string; entry: HistoricalEntry }) {
  const { text } = zoneColors(entry.value);

  return (
    <div className="flex items-center justify-between py-3.5">
      <div>
        <p className="text-sm font-medium text-stone-700">{period}</p>
        <p className={`text-sm ${entry.value != null ? text : 'text-stone-400'}`}>
          {entry.value != null ? entry.label : '—'}
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
