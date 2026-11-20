import { prisma } from '@/lib/prisma';

export interface Trending24h {
  ticker:             string;
  name:               string;
  article_count_24h:  number;
  dominant_sentiment: string;
}

/**
 * Tickers ranked by article volume in the last 24h, with dominant sentiment.
 * Shared by GET /api/trending and the homepage "Saham Trending" strip.
 */
export async function getTrending24h(take = 10): Promise<Trending24h[]> {
  const cutoff = new Date();
  cutoff.setHours(cutoff.getHours() - 24);

  // Article counts per ticker in the last 24h (exclude macro articles with null tickerId)
  const groups = await prisma.news.groupBy({
    by: ['tickerId'],
    where: { publishedAt: { gte: cutoff }, tickerId: { not: null }, category: { not: 'SKIP' } },
    _count: { id: true },
    orderBy: { _count: { id: 'desc' } },
    take,
  });

  if (!groups?.length) return [];

  const tickerIds = groups
    .map(g => g.tickerId)
    .filter((id): id is string => id !== null);

  // Sentiment breakdown per ticker
  const sentimentRows = await prisma.news.findMany({
    where: { tickerId: { in: tickerIds }, publishedAt: { gte: cutoff }, category: { not: 'SKIP' } },
    select: { tickerId: true, sentiment: true },
  });

  const sentMap = new Map<string, Record<string, number>>();
  for (const row of sentimentRows ?? []) {
    if (!row.tickerId) continue;
    if (!sentMap.has(row.tickerId)) sentMap.set(row.tickerId, {});
    const m = sentMap.get(row.tickerId)!;
    m[row.sentiment] = (m[row.sentiment] ?? 0) + 1;
  }

  const dominantSentiment = (tid: string): string => {
    const entries = Object.entries(sentMap.get(tid) ?? {});
    if (entries.length === 0) return 'NEUTRAL';
    return entries.sort((a, b) => b[1] - a[1])[0][0];
  };

  const tickers = await prisma.ticker.findMany({
    where: { id: { in: tickerIds } },
    select: { id: true, symbol: true, name: true },
  });
  const tickerMap = new Map((tickers ?? []).map(t => [t.id, t]));

  const result: Trending24h[] = [];
  for (const g of groups) {
    if (!g.tickerId) continue;
    const t = tickerMap.get(g.tickerId);
    if (!t) continue;
    result.push({
      ticker:             t.symbol,
      name:               t.name,
      article_count_24h:  g._count.id,
      dominant_sentiment: dominantSentiment(g.tickerId),
    });
  }
  return result;
}
