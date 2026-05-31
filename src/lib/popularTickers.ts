import { prisma } from '@/lib/prisma';

const FALLBACK = ['BBCA', 'BBRI', 'BMRI', 'BBNI', 'GOTO', 'TLKM', 'ASII', 'BUMI'];
const MIN_SEARCHES = 20; // switch from fallback to real data once we have enough signal
const WINDOW_DAYS  = 7;
const TOP_N        = 8;

/**
 * Returns the top N most-searched tickers in the last WINDOW_DAYS days.
 * Falls back to the hardcoded list if not enough searches have been logged yet.
 * Safe to call from any server component.
 */
export async function getPopularTickers(): Promise<string[]> {
  try {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - WINDOW_DAYS);

    const total = await prisma.searchLog.count({
      where: { searchedAt: { gte: cutoff } },
    });

    if (total < MIN_SEARCHES) return FALLBACK;

    const groups = await prisma.searchLog.groupBy({
      by: ['tickerSymbol'],
      where: { searchedAt: { gte: cutoff } },
      _count: { id: true },
      orderBy: { _count: { id: 'desc' } },
      take: TOP_N,
    });

    const symbols = groups.map(g => g.tickerSymbol);
    return symbols.length > 0 ? symbols : FALLBACK;
  } catch {
    return FALLBACK; // always degrade gracefully
  }
}
