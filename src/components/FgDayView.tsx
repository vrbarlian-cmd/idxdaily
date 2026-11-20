import { classify } from '@/lib/fearGreed';
import { zoneColors } from '@/lib/zoneColors';
import { COMPONENT_INFO, fmtWib, type FgDay } from '@/lib/fearGreedArchive';

// Server component: score card + component table for one stored F&G day.
// Shared by /fear-greed (latest day) and /fear-greed/[date] (archive day).

export const LABEL_ID: Record<string, string> = {
  'Extreme Fear':  'Ketakutan Ekstrem',
  'Fear':          'Ketakutan',
  'Neutral':       'Netral',
  'Greed':         'Keserakahan',
  'Extreme Greed': 'Keserakahan Ekstrem',
};

export function FgScoreCard({ day, prev, title }: { day: FgDay; prev: FgDay | null; title: string }) {
  const label  = classify(day.score);
  const zone   = zoneColors(day.score);
  const change = prev ? day.score - prev.score : null;
  const prevLabel = prev ? classify(prev.score) : null;

  return (
    <section className="bg-white border border-[#e5e2db] rounded-2xl p-5">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-[#9ca3af] mb-1">{title}</p>
      <div className="flex items-end gap-4 flex-wrap">
        <span className="text-6xl font-bold tabular-nums leading-none" style={{ color: zone.hex }}>
          {Math.round(day.score)}
        </span>
        <div className="pb-1">
          <p className="text-xl font-bold text-[#0f172a] leading-tight">{label}</p>
          <p className="text-sm text-[#6b7280]">{LABEL_ID[label] ?? ''}</p>
        </div>
      </div>
      <p className="text-sm text-[#6b7280] mt-3">
        {change == null ? 'Belum ada data hari sebelumnya.' : (
          <>
            {change > 0 ? 'Naik' : change < 0 ? 'Turun' : 'Tidak berubah'}
            {change !== 0 && <> <span className="font-semibold tabular-nums text-[#0f172a]">{Math.abs(change).toFixed(1)} poin</span></>}
            {' '}dibanding hari bursa sebelumnya ({Math.round(prev!.score)}, {prevLabel}).
          </>
        )}
      </p>
      {day.updatedAt && (
        <p className="text-xs text-[#9ca3af] mt-2">
          Terakhir diperbarui: <time dateTime={day.updatedAt.toISOString()}>{fmtWib(day.updatedAt)}</time>
        </p>
      )}
    </section>
  );
}

export function FgComponentsTable({ day }: { day: FgDay }) {
  if (!day.components.length) {
    return <p className="text-sm text-[#6b7280]">Rincian komponen tidak tersedia untuk hari ini.</p>;
  }
  return (
    <div className="bg-white border border-[#e5e2db] rounded-2xl overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-[#fbfaf8] text-[10px] uppercase tracking-wider text-[#9ca3af]">
          <tr>
            <th className="text-left font-semibold px-4 py-2">Komponen</th>
            <th className="text-right font-semibold px-2 py-2">Bobot</th>
            <th className="text-right font-semibold px-4 py-2">Skor</th>
          </tr>
        </thead>
        <tbody>
          {day.components.map(c => {
            const info  = COMPONENT_INFO[c.id];
            const w     = c.weight ?? info?.fallbackWeight ?? null;
            const zone  = zoneColors(c.score);
            return (
              <tr key={c.id} className="border-t border-[#f0ede8] align-top">
                <td className="px-4 py-2.5">
                  <p className="font-medium text-[#0f172a]">{info?.name ?? c.label}</p>
                  {c.rawLabel && <p className="text-[11px] text-[#9ca3af] mt-0.5 break-words">{c.rawLabel}</p>}
                </td>
                <td className="px-2 py-2.5 text-right tabular-nums text-[#6b7280]">
                  {w != null ? `${Math.round(w * 100)}%` : '—'}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums font-bold" style={{ color: c.score != null ? zone.hex : undefined }}>
                  {c.score != null ? Math.round(c.score) : '—'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function FgDisclaimer() {
  return (
    <p className="text-xs text-[#9ca3af] leading-relaxed">
      Fear &amp; Greed Index IHSG adalah indikator sentimen untuk informasi saja, bukan saran
      investasi dan bukan rekomendasi jual/beli saham. Keputusan investasi sepenuhnya
      tanggung jawab Anda.
    </p>
  );
}
