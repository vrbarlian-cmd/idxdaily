import { unstable_cache } from 'next/cache';
import { prisma } from '@/lib/prisma';
import { mentionFilter } from '@/lib/mentionWhere';

/**
 * A ticker page is indexable (in the sitemap, robots=index) only when it has
 * at least this many non-SKIP, enriched articles in the last 30 days. Thinner
 * pages stay reachable but get robots noindex,follow.
 */
export const INDEX_MIN_ARTICLES_30D = 3;

export const SITE_URL = 'https://www.dailyihsg.com';

export interface TickerIndexStat {
  symbol:      string;
  name:        string;
  sector:      string | null;
  count30d:    number;
  newestAt:    Date | null;   // created_at of the newest counted article
}

function cutoff30d(): Date {
  return new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);
}

/**
 * 30-day article counts for every ticker_tag_enabled ticker, using the exact
 * same mention filter as the ticker page (mentionFilter, includeMacro=true).
 * Never throws: on any DB error it returns an empty list so the caller can
 * degrade (sitemap without tickers, no trending strip) instead of crashing.
 */
async function loadTickerIndexStats(): Promise<TickerIndexStat[]> {
  try {
    // ticker_tag_enabled is not mapped in the Prisma schema — raw query.
    const tickers = await prisma.$queryRaw<
      Array<{ id: string; symbol: string; name: string; sector: string | null }>
    >`SELECT id, symbol, name, sector FROM tickers WHERE ticker_tag_enabled = TRUE`;
    if (!tickers?.length) return [];

    const since = cutoff30d();
    const groups = await prisma.tickerMention.groupBy({
      by: ['tickerId'],
      where: { ...mentionFilter(undefined, since, null, true), tickerId: { in: tickers.map(t => t.id) } },
      _count: { _all: true },
    });
    const countMap = new Map(groups.map(g => [g.tickerId, g._count?._all ?? 0]));

    // Newest article created_at per ticker (sitemap lastmod). Mirrors
    // mentionFilter(includeMacro=true); Prisma groupBy cannot aggregate a
    // relation field, so this one aggregate is raw SQL.
    const newestRows = await prisma.$queryRaw<Array<{ ticker_id: string; newest: Date | null }>>`
      SELECT m.ticker_id, MAX(a.created_at) AS newest
      FROM ticker_mentions m
      JOIN articles a ON a.id = m.article_id
      WHERE (m.match_confidence IN ('high', 'medium') OR m.match_type = 'macro_impact')
        AND a.ai_summary IS NOT NULL
        AND a.published_at IS NOT NULL
        AND a.category IS DISTINCT FROM 'SKIP'
        AND a.published_at >= ${since}
      GROUP BY m.ticker_id
    `;
    const newestMap = new Map((newestRows ?? []).map(r => [r.ticker_id, r.newest]));

    return tickers.map(t => ({
      symbol:   t.symbol,
      name:     t.name,
      sector:   t.sector,
      count30d: countMap.get(t.id) ?? 0,
      newestAt: newestMap.get(t.id) ?? null,
    }));
  } catch (err) {
    console.error('[tickerSeo] loadTickerIndexStats failed:', err);
    return [];
  }
}

/**
 * Cached for 1 hour — used by the sitemap, the homepage trending strip and
 * related-ticker links, so it must not hit the DB on every request.
 * Dates are serialised by the cache, so they are revived below.
 */
const cachedStats = unstable_cache(
  async () => (await loadTickerIndexStats()).map(s => ({
    ...s,
    newestAt: s.newestAt ? s.newestAt.toISOString() : null,
  })),
  ['ticker-index-stats-v1'],
  { revalidate: 3600 },
);

export async function getTickerIndexStats(): Promise<TickerIndexStat[]> {
  try {
    const rows = await cachedStats();
    return (rows ?? []).map(r => ({ ...r, newestAt: r.newestAt ? new Date(r.newestAt) : null }));
  } catch (err) {
    console.error('[tickerSeo] getTickerIndexStats failed:', err);
    return [];
  }
}

export async function getIndexableSymbols(): Promise<Set<string>> {
  const stats = await getTickerIndexStats();
  return new Set(stats.filter(s => s.count30d >= INDEX_MIN_ARTICLES_30D).map(s => s.symbol));
}
