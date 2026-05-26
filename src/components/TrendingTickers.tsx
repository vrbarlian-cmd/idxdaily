import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { prisma } from '@/lib/prisma';
import Link from 'next/link';

// ── Sentiment chip ────────────────────────────────────────────────────────────

function SentimentChip({ sentiment, enriched }: { sentiment: string; enriched: boolean }) {
  if (!enriched) {
    return (
      <span className="text-xs text-stone-400 bg-stone-100 rounded-full px-2 py-0.5 font-medium">
        —
      </span>
    );
  }
  if (sentiment === 'BULLISH') {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-full px-2 py-0.5 font-semibold">
        <TrendingUp className="w-3 h-3" />
        Bull
      </span>
    );
  }
  if (sentiment === 'BEARISH') {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-red-600 bg-red-50 border border-red-200 rounded-full px-2 py-0.5 font-semibold">
        <TrendingDown className="w-3 h-3" />
        Bear
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-2 py-0.5 font-medium">
      <Minus className="w-3 h-3" />
      Net
    </span>
  );
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
    // Only count enriched articles in sentiment distribution — unenriched articles
    // sit at the DB default 'NEUTRAL' and would falsely inflate the neutral count.
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

  function barColor(s: string) {
    if (s === 'BULLISH') return 'bg-emerald-400';
    if (s === 'BEARISH') return 'bg-red-400';
    return 'bg-amber-400';
  }

  return (
    <div className="bg-white border border-stone-200 rounded-2xl p-5 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-emerald-500" />
          <p className="text-sm font-bold text-stone-800">Trending Tickers</p>
        </div>
        <p className="text-xs text-stone-400">7d · volume</p>
      </div>

      {items.length === 0 ? (
        <p className="text-stone-400 text-sm">Belum ada data.</p>
      ) : (
        <div className="space-y-1.5">
          {items.map(({ ticker, count, sentiment, enriched }) => {
            const isActive = currentTicker === ticker.symbol;
            const widthPct = Math.max(8, Math.round((count / maxCount) * 100));

            return (
              <Link
                key={ticker.id}
                href={`/saham/${ticker.symbol}`}
                className={`group flex items-center gap-3 py-2 px-2 rounded-xl transition-all ${
                  isActive
                    ? 'bg-brand-50 border border-brand-100'
                    : 'hover:bg-stone-50 border border-transparent'
                }`}
              >
                {/* Ticker badge */}
                <span className={`inline-flex items-center justify-center w-12 h-7 rounded-lg font-mono text-xs font-bold flex-shrink-0 transition-colors ${
                  isActive
                    ? 'bg-brand-600 text-white'
                    : 'bg-stone-800 text-white group-hover:bg-stone-700'
                }`}>
                  {ticker.symbol}
                </span>

                {/* Name + bar */}
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-stone-600 truncate mb-1">{ticker.name}</p>
                  {/* Volume bar */}
                  <div className="h-1 bg-stone-100 rounded-full overflow-hidden">
                    <div
                      className={`h-1 rounded-full transition-all ${barColor(sentiment)}`}
                      style={{ width: `${widthPct}%` }}
                    />
                  </div>
                </div>

                {/* Right side */}
                <div className="flex items-center gap-1.5 flex-shrink-0">
                  <SentimentChip sentiment={sentiment} enriched={enriched} />
                  <span className="text-xs text-stone-400 tabular-nums w-5 text-right font-medium">
                    {count}
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
