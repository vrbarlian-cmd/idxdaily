import { prisma } from '@/lib/prisma';
import Link from 'next/link';

// ── Helpers ───────────────────────────────────────────────────────────────────

function sentimentDot(s: string) {
  if (s === 'BULLISH') return 'bg-emerald-500';
  if (s === 'BEARISH') return 'bg-red-500';
  return 'bg-amber-400';
}
function sentimentText(s: string) {
  if (s === 'BULLISH') return 'text-emerald-700';
  if (s === 'BEARISH') return 'text-red-600';
  return 'text-amber-700';
}
function sentimentLabel(s: string) {
  if (s === 'BULLISH') return 'Bull';
  if (s === 'BEARISH') return 'Bear';
  return 'Net';
}
function barColor(s: string) {
  if (s === 'BULLISH') return 'bg-emerald-400';
  if (s === 'BEARISH') return 'bg-red-400';
  return 'bg-amber-400';
}

// ── Main component ────────────────────────────────────────────────────────────

export default async function TrendingTickers({ currentTicker }: { currentTicker?: string }) {
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - 7);

  const groups = await prisma.news.groupBy({
    by: ['tickerId'],
    where: { publishedAt: { gte: cutoff }, tickerId: { not: null } },
    _count: { id: true },
    orderBy: { _count: { id: 'desc' } },
    take: 10,
  });

  const tickerIds = groups.map(g => g.tickerId).filter((id): id is string => id !== null);

  const articles = await prisma.news.findMany({
    where: { tickerId: { in: tickerIds }, publishedAt: { gte: cutoff } },
    select: { tickerId: true, sentiment: true, impactScore: true, aiSummary: true },
  });

  const tickerStats = new Map<string, { sentiments: Record<string, number>; enriched: number }>();
  for (const a of articles) {
    if (!a.tickerId) continue;
    if (!tickerStats.has(a.tickerId)) tickerStats.set(a.tickerId, { sentiments: {}, enriched: 0 });
    const s = tickerStats.get(a.tickerId)!;
    if (a.aiSummary) {
      s.sentiments[a.sentiment] = (s.sentiments[a.sentiment] ?? 0) + 1;
      s.enriched++;
    }
  }

  const dominant = (tid: string) => {
    const m = tickerStats.get(tid)?.sentiments ?? {};
    const entries = Object.entries(m);
    if (!entries.length) return 'NEUTRAL';
    return entries.sort((a, b) => b[1] - a[1])[0][0];
  };

  const hasEnriched = (tid: string) => (tickerStats.get(tid)?.enriched ?? 0) > 0;

  const tickers = await prisma.ticker.findMany({
    where: { id: { in: tickerIds } },
    select: { id: true, symbol: true, name: true },
  });
  const tickerMap = new Map(tickers.map(t => [t.id, t]));

  const items = groups
    .filter((g): g is typeof g & { tickerId: string } => g.tickerId !== null)
    .map(g => ({
      ticker:    tickerMap.get(g.tickerId),
      count:     g._count.id,
      sentiment: dominant(g.tickerId),
      enriched:  hasEnriched(g.tickerId),
    }))
    .filter((i): i is typeof i & { ticker: NonNullable<typeof i.ticker> } => !!i.ticker);

  const maxCount = Math.max(...items.map(i => i.count), 1);

  return (
    <section>

      {/* Section header */}
      <div className="flex items-center justify-between mb-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-[#9ca3af] mb-0.5">
            7 Hari Terakhir
          </p>
          <h2 className="text-sm font-bold text-[#0f172a]">Trending Tickers</h2>
        </div>
        <span className="text-[11px] text-[#9ca3af]">volume berita</span>
      </div>

      <hr className="border-[#e5e2db] mb-4" />

      {items.length === 0 ? (
        <p className="text-[#9ca3af] text-sm py-4">Belum ada data.</p>
      ) : (
        /* Horizontal scroll strip */
        <div
          className="flex gap-2.5 overflow-x-auto pb-1"
          style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
        >
          {items.map(({ ticker, count, sentiment, enriched }) => {
            const isActive  = currentTicker === ticker.symbol;
            const widthPct  = Math.max(10, Math.round((count / maxCount) * 100));

            return (
              <Link
                key={ticker.id}
                href={`/saham/${ticker.symbol}`}
                className={`
                  group flex-shrink-0 w-36 rounded-xl border p-3 transition-all duration-150
                  hover:shadow-sm
                  ${isActive
                    ? 'bg-blue-50 border-blue-200'
                    : 'bg-white border-[#e5e2db] hover:border-[#d1cdc7]'}
                `}
              >
                {/* Symbol + count */}
                <div className="flex items-start justify-between mb-1.5">
                  <span className={`font-mono text-xs font-bold ${
                    isActive ? 'text-[#1a56db]' : 'text-[#0f172a] group-hover:text-[#1a56db]'
                  } transition-colors`}>
                    {ticker.symbol}
                  </span>
                  <span className="text-[10px] text-[#9ca3af] tabular-nums font-medium">
                    {count}
                  </span>
                </div>

                {/* Company name */}
                <p className="text-[11px] text-[#6b7280] truncate mb-2 leading-tight">
                  {ticker.name}
                </p>

                {/* Volume bar */}
                <div className="h-1 bg-[#f0ede8] rounded-full overflow-hidden mb-2">
                  <div
                    className={`h-1 rounded-full transition-all ${barColor(sentiment)}`}
                    style={{ width: `${widthPct}%` }}
                  />
                </div>

                {/* Sentiment */}
                {enriched ? (
                  <div className={`flex items-center gap-1 text-[10px] font-semibold ${sentimentText(sentiment)}`}>
                    <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${sentimentDot(sentiment)}`} />
                    {sentimentLabel(sentiment)}
                  </div>
                ) : (
                  <span className="text-[10px] text-[#9ca3af]">—</span>
                )}
              </Link>
            );
          })}
        </div>
      )}
    </section>
  );
}
