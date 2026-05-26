import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

// GET /api/trending
// Returns tickers ranked by article volume in the last 24h, with dominant sentiment.
export async function GET() {
  const cutoff = new Date();
  cutoff.setHours(cutoff.getHours() - 24);

  // Article counts per ticker in the last 24h (exclude macro articles with null tickerId)
  const groups = await prisma.news.groupBy({
    by: ['tickerId'],
    where: { publishedAt: { gte: cutoff }, tickerId: { not: null } },
    _count: { id: true },
    orderBy: { _count: { id: 'desc' } },
    take: 10,
  });

  if (groups.length === 0) {
    return NextResponse.json({ tickers: [], window_hours: 24 });
  }

  const tickerIds = groups
    .map(g => g.tickerId)
    .filter((id): id is string => id !== null);

  // Sentiment breakdown per ticker
  const sentimentRows = await prisma.news.findMany({
    where: { tickerId: { in: tickerIds }, publishedAt: { gte: cutoff } },
    select: { tickerId: true, sentiment: true },
  });

  // Build sentiment counts map: tickerId → { BULLISH, BEARISH, NEUTRAL }
  const sentMap = new Map<string, Record<string, number>>();
  for (const row of sentimentRows) {
    if (!row.tickerId) continue;
    if (!sentMap.has(row.tickerId)) sentMap.set(row.tickerId, {});
    const m = sentMap.get(row.tickerId)!;
    m[row.sentiment] = (m[row.sentiment] ?? 0) + 1;
  }

  const dominantSentiment = (tid: string): string => {
    const m = sentMap.get(tid) ?? {};
    const entries = Object.entries(m);
    if (entries.length === 0) return 'NEUTRAL';
    return entries.sort((a, b) => b[1] - a[1])[0][0];
  };

  // Fetch ticker details
  const tickers = await prisma.ticker.findMany({
    where: { id: { in: tickerIds } },
    select: { id: true, symbol: true, name: true },
  });
  const tickerMap = new Map(tickers.map(t => [t.id, t]));

  const result = groups
    .filter((g): g is typeof g & { tickerId: string } => g.tickerId !== null)
    .map(g => {
      const t = tickerMap.get(g.tickerId);
      if (!t) return null;
      return {
        ticker: t.symbol,
        name: t.name,
        article_count_24h: g._count.id,
        dominant_sentiment: dominantSentiment(g.tickerId),
      };
    })
    .filter(Boolean);

  return NextResponse.json({ tickers: result, window_hours: 24 });
}
