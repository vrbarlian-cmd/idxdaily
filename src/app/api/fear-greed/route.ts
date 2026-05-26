import { NextResponse } from 'next/server';
import { computeFearGreed } from '@/lib/fearGreed';

// GET /api/fear-greed?days=7
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const days = Math.min(parseInt(searchParams.get('days') || '7', 10), 90);

  const data = await computeFearGreed(days);

  return NextResponse.json({
    value:      data.score,
    label:      data.label,
    updated_at: new Date().toISOString(),
    active_components: data.activeComponents,
    components: Object.fromEntries(
      data.components.map(c => [
        c.id,
        {
          value:  c.score,
          weight: c.weight,
          status: c.status,
          raw:    c.raw,
          label:  c.rawLabel,
          note:   c.note,
        },
      ])
    ),
    // Article sentiment (raw signal used in headline component)
    article_sentiment: {
      bullish_pct:    data.bullishPct,
      bearish_pct:    data.bearishPct,
      neutral_pct:    data.neutralPct,
      article_count:  data.articleCount,
      enriched_count: data.enrichedCount,
      days,
    },
  });
}
