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
  const now       = Date.now();
  const cutoff7d  = new Date(now - 7  * 24 * 60 * 60 * 1000);
  const cutoff24h = new Date(now - 24 * 60 * 60 * 1000);
  const cutoff48h = new Date(now - 48 * 60 * 60 * 1000);

  // Use tickerMention table (same as ticker page) — high+medium confidence only
  const mentions = await prisma.tickerMention.findMany({
    where: {
      matchConfidence: { in: ['high', 'medium'] },
      article: { publishedAt: { gte: cutoff7d } },
    },
    select: {
      tickerId:  true,
      sentiment: true,
      article: {
        select: {
          publishedAt: true,
          aiSummary:   true,
        },
      },
    },
  });

  // Compute recency-weighted score + dominant sentiment per ticker
  // Weights: 24h articles = 3×, 24-48h = 1.5×, older = 1×
  type TickerStat = {
    score:      number;                    // recency-weighted rank score
    rawCount:   number;                    // raw 7d article count (for display)
    sentiments: Record<string, number>;    // weighted sentiment votes
    enriched:   boolean;
  };

  const tickerStats = new Map<string, TickerStat>();

  for (const m of mentions) {
    if (!m.tickerId) continue;

    const pub = m.article?.publishedAt;
    let weight = 1.0;
    if (pub) {
      if (pub >= cutoff24h)      weight = 3.0;
      else if (pub >= cutoff48h) weight = 1.5;
    }

    if (!tickerStats.has(m.tickerId)) {
      tickerStats.set(m.tickerId, { score: 0, rawCount: 0, sentiments: {}, enriched: false });
    }
    const stat = tickerStats.get(m.tickerId)!;
    stat.score    += weight;
    stat.rawCount += 1;

    // Only count sentiment when article is AI-enriched (same condition as ticker page)
    if (m.article?.aiSummary && m.sentiment) {
      stat.sentiments[m.sentiment] = (stat.sentiments[m.sentiment] ?? 0) + 1;
      stat.enriched = true;
    }
  }

  // Sort by recency-weighted score, take top 10
  const topEntries = Array.from(tickerStats.entries())
    .sort((a, b) => b[1].score - a[1].score)
    .slice(0, 10);

  const tickerIds = topEntries.map(([id]) => id);

  const tickers = await prisma.ticker.findMany({
    where:  { id: { in: tickerIds } },
    select: { id: true, symbol: true, name: true },
  });
  const tickerMap = new Map(tickers.map(t => [t.id, t]));

  // Dominant sentiment = most-voted sentiment among enriched mentions
  const dominant = (sentiments: Record<string, number>): string => {
    const entries = Object.entries(sentiments);
    if (!entries.length) return 'NEUTRAL';
    return entries.sort((a, b) => b[1] - a[1])[0][0];
  };

  const items = topEntries
    .map(([id, stat]) => ({
      ticker:    tickerMap.get(id),
      count:     stat.rawCount,
      sentiment: dominant(stat.sentiments),
      enriched:  stat.enriched,
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
        /* Horizontal scroll strip with right-fade affordance */
        <div className="relative">
          {/* Right-edge fade — hints "more content" without JS */}
          <div
            className="pointer-events-none absolute right-0 top-0 bottom-1 w-12 z-10"
            style={{ background: 'linear-gradient(to left, #f8f7f4 10%, transparent 100%)' }}
          />

          <div
            className="flex gap-2.5 overflow-x-auto pb-2 [&::-webkit-scrollbar]:hidden"
            style={{
              scrollbarWidth:          'none',
              msOverflowStyle:         'none',
              WebkitOverflowScrolling: 'touch',
              scrollSnapType:          'x mandatory',
              paddingRight:            '3rem',
            }}
          >
          {items.map(({ ticker, count, sentiment, enriched }) => {
            const isActive  = currentTicker === ticker.symbol;
            const widthPct  = Math.max(10, Math.round((count / maxCount) * 100));

            return (
              <Link
                key={ticker.id}
                href={`/saham/${ticker.symbol}`}
                style={{ scrollSnapAlign: 'start' }}
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
        </div>
      )}
    </section>
  );
}
