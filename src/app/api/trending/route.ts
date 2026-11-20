import { NextResponse } from 'next/server';
import { getTrending24h } from '@/lib/trending';

export const dynamic = 'force-dynamic';

// GET /api/trending
// Returns tickers ranked by article volume in the last 24h, with dominant sentiment.
export async function GET() {
  const tickers = await getTrending24h(10);
  return NextResponse.json({ tickers, window_hours: 24 });
}
