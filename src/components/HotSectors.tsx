import { Flame } from 'lucide-react';
import { prisma } from '@/lib/prisma';
import { Prisma } from '@prisma/client';

export default async function HotSectors() {
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - 7);

  // Get all tickers that have a sector assigned
  const tickers = await prisma.ticker.findMany({
    select: { id: true, sector: true },
    where:  { sector: { not: null } },
  });

  if (tickers.length === 0) {
    return (
      <div className="bg-white border border-stone-200 rounded-2xl p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-2">
          <Flame className="w-4 h-4 text-amber-500" />
          <p className="text-sm font-bold text-stone-800">Hot Sectors</p>
        </div>
        <p className="text-sm text-stone-400">Belum ada data sektor.</p>
      </div>
    );
  }

  const sectorMap = new Map(tickers.map(t => [t.id, t.sector!]));
  const tickerIds = tickers.map(t => t.id);

  // ── Broader coverage: collect articles via BOTH direct ticker_id AND ticker_mentions ──
  // This catches articles where the sector ticker is a secondary mention (not the primary).

  // Direct: articles whose primary ticker is sector-tagged
  const directArticles = await prisma.news.findMany({
    where:  { tickerId: { in: tickerIds, not: null }, publishedAt: { gte: cutoff } },
    select: { id: true, tickerId: true, sentiment: true, impactScore: true },
  });

  // Via mentions: articles that mention a sector ticker (deduped by article id).
  // Cast ticker_id::text on the column side so Prisma's string parameters match.
  const uuidTextList = Prisma.join(tickerIds);
  const mentionedRaw = await prisma.$queryRaw<
    Array<{ article_id: string; ticker_id: string; sentiment: string; impact_score: number }>
  >`
    SELECT DISTINCT ON (a.id, tm.ticker_id)
           a.id            AS article_id,
           tm.ticker_id::text AS ticker_id,
           a.sentiment,
           a.impact_score
    FROM   ticker_mentions tm
    JOIN   articles a ON a.id = tm.article_id
    WHERE  tm.ticker_id::text IN (${uuidTextList})
      AND  a.published_at >= ${cutoff}
  `;

  // Merge: use a Set of (article_id + ticker_id) to avoid double-counting
  interface Row { tickerId: string; sentiment: string; impactScore: number }
  const seen = new Set<string>();
  const allRows: Row[] = [];

  for (const a of directArticles) {
    const key = `${a.id}:${a.tickerId}`;
    if (!seen.has(key) && a.tickerId) {
      seen.add(key);
      allRows.push({ tickerId: a.tickerId, sentiment: a.sentiment, impactScore: a.impactScore });
    }
  }
  for (const m of mentionedRaw) {
    const key = `${m.article_id}:${m.ticker_id}`;
    if (!seen.has(key)) {
      seen.add(key);
      allRows.push({ tickerId: m.ticker_id, sentiment: m.sentiment, impactScore: m.impact_score });
    }
  }

  // ── Aggregate by sector ───────────────────────────────────────────────────────
  const sectorRows = new Map<string, { sentiment: string; impactScore: number }[]>();
  for (const row of allRows) {
    const sector = sectorMap.get(row.tickerId);
    if (!sector) continue;
    if (!sectorRows.has(sector)) sectorRows.set(sector, []);
    sectorRows.get(sector)!.push({ sentiment: row.sentiment, impactScore: row.impactScore });
  }

  const sectors = Array.from(sectorRows.entries())
    .map(([sector, rows]) => {
      const wBull = rows.filter(r => r.sentiment === 'BULLISH').reduce((s, r) => s + r.impactScore, 0);
      const wBear = rows.filter(r => r.sentiment === 'BEARISH').reduce((s, r) => s + r.impactScore, 0);
      const wNeut = rows.filter(r => r.sentiment === 'NEUTRAL').reduce((s, r) => s + r.impactScore * 0.5, 0);
      const totalW = wBull + wBear + wNeut;
      const raw    = totalW === 0 ? 0 : (wBull - wBear) / totalW;
      const score  = Math.round(((raw + 1) / 2) * 100);
      return { sector, score, count: rows.length };
    })
    .sort((a, b) => b.count - a.count)   // rank by article volume
    .slice(0, 8);

  if (sectors.length === 0) {
    return (
      <div className="bg-white border border-stone-200 rounded-2xl p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-2">
          <Flame className="w-4 h-4 text-amber-500" />
          <p className="text-sm font-bold text-stone-800">Hot Sectors</p>
        </div>
        <p className="text-sm text-stone-400">Belum ada berita sektor minggu ini.</p>
      </div>
    );
  }

  return (
    <div className="bg-white border border-stone-200 rounded-2xl p-5 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Flame className="w-4 h-4 text-amber-500" />
          <p className="text-sm font-bold text-stone-800">Hot Sectors</p>
        </div>
        <p className="text-xs text-stone-400">7d · volume</p>
      </div>

      <div className="space-y-4">
        {sectors.map(({ sector, score, count }) => {
          const signed  = score - 50;
          const isBull  = signed >= 0;
          const pct     = Math.abs(signed) * 2;
          const signStr = isBull ? `+${signed}` : String(signed);

          const scoreColor = isBull ? 'text-emerald-700' : 'text-red-600';
          const barColor   = isBull ? 'bg-emerald-500'   : 'bg-red-500';

          return (
            <div key={sector}>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-sm font-medium text-stone-700 truncate">{sector}</span>
                <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                  <span className="text-xs text-stone-400">{count} artikel</span>
                  <span className={`text-sm font-bold tabular-nums w-8 text-right ${scoreColor}`}>
                    {signStr}
                  </span>
                </div>
              </div>

              {/* Center-anchored sentiment bar */}
              <div className="h-2 bg-stone-100 rounded-full relative overflow-hidden">
                {isBull ? (
                  <div
                    className={`absolute top-0 bottom-0 rounded-r-full ${barColor}`}
                    style={{ left: '50%', width: `${pct / 2}%` }}
                  />
                ) : (
                  <div
                    className={`absolute top-0 bottom-0 rounded-l-full ${barColor}`}
                    style={{ right: '50%', width: `${pct / 2}%` }}
                  />
                )}
                <div className="absolute top-0 bottom-0 w-px bg-stone-300" style={{ left: '50%' }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
