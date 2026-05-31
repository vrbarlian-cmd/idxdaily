import type { HistoricalValues, HistoricalEntry } from '@/lib/fearGreed';
import { zoneColors } from '@/lib/zoneColors';

// ── Single cell ───────────────────────────────────────────────────────────────

function HistCell({ period, entry }: { period: string; entry: HistoricalEntry }) {
  const { text } = zoneColors(entry.value);

  return (
    <div className="p-4">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-[#9ca3af] mb-1.5">
        {period}
      </p>
      <p className={`text-2xl font-black leading-none tabular-nums mb-1 ${
        entry.value != null ? text : 'text-[#d1cdc7]'
      }`}>
        {entry.value != null ? Math.round(entry.value) : '—'}
      </p>
      <p className={`text-[11px] font-medium ${
        entry.value != null ? text : 'text-[#9ca3af]'
      }`}>
        {entry.value != null ? entry.label : 'No data'}
      </p>
    </div>
  );
}

// ── Panel (borderless — outer card provided by page.tsx) ─────────────────────

export default function FearGreedHistorical({ data }: { data: HistoricalValues }) {
  const rows: { period: string; entry: HistoricalEntry }[] = [
    { period: 'Now',        entry: data.now       },
    { period: 'Yesterday',  entry: data.yesterday },
    { period: 'Last Week',  entry: data.lastWeek  },
    { period: 'Last Month', entry: data.lastMonth },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Section label */}
      <div className="px-5 pt-5 pb-3">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-[#9ca3af] mb-0.5">
          Historical Comparison
        </p>
        <h2 className="text-sm font-bold text-[#0f172a]">Fear &amp; Greed Over Time</h2>
      </div>

      {/* 2×2 grid */}
      <div className="flex-1 grid grid-cols-2 divide-x divide-y divide-[#f0ede8] border-t border-[#f0ede8]">
        {rows.map(({ period, entry }) => (
          <HistCell key={period} period={period} entry={entry} />
        ))}
      </div>
    </div>
  );
}
