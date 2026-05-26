import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export interface FearGreedHistoryPoint {
  date:          string;   // YYYY-MM-DD
  fgSmoothed:    number | null;
  fgRaw:         number | null;
  label:         string;
  ihsgClose:     number | null;
  isBackfilled:  boolean;
}

// GET /api/fear-greed-history?days=30|90|all
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const daysParam = searchParams.get('days') || '30';
  const isAll = daysParam === 'all';
  // For "all", use 3650 days (10 years) — effectively unbounded
  const days = isAll ? 3650 : Math.max(7, Math.min(365, parseInt(daysParam, 10)));

  // Fetch F&G history with is_backfilled flag
  const fgRows = await prisma.$queryRaw<
    Array<{
      date:           Date;
      score:          number | null;
      raw_score:      number | null;
      smoothed_score: number | null;
      label:          string;
      is_backfilled:  boolean;
    }>
  >`
    SELECT date, score, raw_score, smoothed_score, label,
           COALESCE(is_backfilled, FALSE) AS is_backfilled
    FROM fear_greed_index
    WHERE date >= CURRENT_DATE - ${days}::int
    ORDER BY date ASC
  `;

  // Fetch IHSG close prices for the same window
  // Cast to float8 (double precision) to guarantee node-postgres returns a JS number,
  // not a Decimal or other type, regardless of the stored column type (REAL/float4).
  const ihsgRows = await prisma.$queryRaw<
    Array<{ date: Date; close: number }>
  >`
    SELECT date, close::float8 AS close
    FROM ihsg_daily
    WHERE date >= CURRENT_DATE - ${days}::int
    ORDER BY date ASC
  `;

  // Build IHSG lookup map
  // Guard: IHSG has traded between ~1,000-10,000 historically; reject any value
  // outside [1000, 15000] as a corrupt/scaled value rather than silently storing it.
  const IHSG_MIN = 1000;
  const IHSG_MAX = 15000;
  const ihsgMap = new Map<string, number>();
  for (const r of ihsgRows) {
    const key = r.date instanceof Date
      ? r.date.toISOString().slice(0, 10)
      : String(r.date).slice(0, 10);
    const val = Number(r.close);
    if (isFinite(val) && val >= IHSG_MIN && val <= IHSG_MAX) {
      ihsgMap.set(key, val);
    }
  }

  const points: FearGreedHistoryPoint[] = fgRows.map(r => {
    const dateStr = r.date instanceof Date
      ? r.date.toISOString().slice(0, 10)
      : String(r.date).slice(0, 10);

    // Only fall back to score when raw_score is also present, which means the row
    // was properly computed (not a stale legacy entry with an unreliable score value).
    const fgSmoothed = r.smoothed_score ?? (r.raw_score != null ? r.score : null) ?? null;
    const fgRaw      = r.raw_score ?? null;

    return {
      date:          dateStr,
      fgSmoothed:    fgSmoothed !== null ? Number(fgSmoothed) : null,
      fgRaw:         fgRaw      !== null ? Number(fgRaw)      : null,
      label:         r.label,
      ihsgClose:     ihsgMap.get(dateStr) ?? null,
      isBackfilled:  Boolean(r.is_backfilled),
    };
  });

  return NextResponse.json({ points, days });
}
