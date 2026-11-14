import { Clock } from 'lucide-react';
import type { HistoricalValues, HistoricalEntry } from '@/lib/fearGreed';
import { zoneColors } from '@/lib/zoneColors';

// Same thresholds as the gauge and the backend's classify() — keep it that way.
function zone(score: number | null): { color: string; label: string } {
  if (score == null) return { color: '#A8A29E', label: '—' };
  const { hex, label } = zoneColors(score);
  return { color: hex, label };
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
    <>
      {/* Phones: one compact row of four values */}
      <div className="md:hidden bg-white border border-stone-200 rounded-xl px-2 py-3">
        <div className="grid grid-cols-4 divide-x divide-stone-100">
          {rows.map(({ period, entry }) => {
            const { color, label } = zone(entry.value);
            return (
              <div key={period} className="flex flex-col items-center gap-1 px-1 text-center">
                <span className="text-[10px] font-medium text-stone-500 leading-tight">{period}</span>
                <span className="text-lg font-bold tabular-nums leading-none" style={{ color }}>
                  {entry.value != null ? Math.round(entry.value) : '—'}
                </span>
                <span className="text-[10px] leading-tight" style={{ color }}>
                  {entry.value != null ? label : '—'}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Tablet & desktop: full card */}
      <HistoricalCard rows={rows} />
    </>
  );
}

function HistoricalCard({ rows }: { rows: { period: string; entry: HistoricalEntry }[] }) {
  return (
    <div className="hidden md:block bg-white border border-stone-200 rounded-xl p-5">
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
