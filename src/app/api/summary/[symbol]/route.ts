import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export const dynamic = 'force-dynamic';

// ── In-memory response cache ──────────────────────────────────────────────────
// One DB round-trip per symbol per 60 s. Module-level: persists across
// requests on the same serverless instance and works on long-running servers.
// Prevents abusive polling and reduces Neon cold-start costs.
interface CacheEntry {
  lastCall:   number;
  lastResult: unknown;
}
const symbolCache = new Map<string, CacheEntry>();
const CACHE_TTL_MS = 60_000; // 60 seconds

export async function GET(
  _request: NextRequest,
  { params }: { params: { symbol: string } }
) {
  // ── Input validation ───────────────────────────────────────────────────────
  const symbol = params.symbol.toUpperCase();
  if (!/^[A-Z]{2,6}$/.test(symbol)) {
    return NextResponse.json({ error: 'Invalid symbol' }, { status: 400 });
  }

  // ── Cache hit — return immediately, no DB call ─────────────────────────────
  const now    = Date.now();
  const cached = symbolCache.get(symbol);
  if (cached && now - cached.lastCall < CACHE_TTL_MS) {
    return NextResponse.json(cached.lastResult);
  }

  // ── DB query ───────────────────────────────────────────────────────────────
  const ticker = await prisma.ticker.findUnique({ where: { symbol } });
  if (!ticker) {
    return NextResponse.json({ error: 'Ticker not found' }, { status: 404 });
  }

  const sentimentCounts = await prisma.news.groupBy({
    by: ['sentiment'],
    where: { tickerId: ticker.id },
    _count: true,
  });

  const distribution = { BULLISH: 0, BEARISH: 0, NEUTRAL: 0 };
  sentimentCounts.forEach((item) => {
    if (item.sentiment in distribution) {
      distribution[item.sentiment as keyof typeof distribution] = item._count;
    }
  });

  const avgImpact = await prisma.news.aggregate({
    where: { tickerId: ticker.id },
    _avg: { impactScore: true },
  });

  const result = {
    ticker,
    sentimentDistribution: distribution,
    averageImpactScore: avgImpact._avg.impactScore ?? 5,
    newsCount: sentimentCounts.reduce((s, r) => s + r._count, 0),
  };

  // ── Update cache ───────────────────────────────────────────────────────────
  symbolCache.set(symbol, { lastCall: now, lastResult: result });

  return NextResponse.json(result);
}
