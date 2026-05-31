import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export const dynamic = 'force-dynamic';

// POST /api/search-log  { symbol: "BBCA" }
// Fire-and-forget — logs ticker searches for Populer ranking.
// Only stores symbol + timestamp. No user identifiers.
export async function POST(req: Request) {
  try {
    const body = await req.json();
    const symbol = typeof body?.symbol === 'string'
      ? body.symbol.trim().toUpperCase()
      : null;

    if (!symbol || symbol.length < 1 || symbol.length > 10 || !/^[A-Z0-9]+$/.test(symbol)) {
      return NextResponse.json({ ok: false }, { status: 400 });
    }

    await prisma.searchLog.create({ data: { tickerSymbol: symbol } });

    return NextResponse.json({ ok: true });
  } catch {
    // Non-critical — never surface logging errors to the client
    return NextResponse.json({ ok: false }, { status: 500 });
  }
}
