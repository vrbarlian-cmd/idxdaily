import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export const dynamic = 'force-dynamic';

// ── IP-based write throttle ───────────────────────────────────────────────────
// Max 10 writes per IP per 60 s. Prevents bots from flooding the search_log
// table and gaming the Populer / Trending ranking.
interface IpEntry {
  windowStart: number;
  count:       number;
}
const ipMap     = new Map<string, IpEntry>();
const WINDOW_MS  = 60_000; // 60 seconds
const MAX_WRITES = 10;

function getIp(req: NextRequest): string {
  // x-forwarded-for is set by Vercel's edge; fall back to x-real-ip or unknown.
  return (
    req.headers.get('x-forwarded-for')?.split(',')[0].trim() ??
    req.headers.get('x-real-ip') ??
    'unknown'
  );
}

// POST /api/search-log  { symbol: "BBCA" }
// Fire-and-forget — logs ticker searches for Populer ranking.
// Only stores symbol + timestamp. No user identifiers.
export async function POST(req: NextRequest) {
  try {
    const { symbol } = await req.json();

    // ── Input validation ─────────────────────────────────────────────────────
    if (!symbol || !/^[A-Z]{1,6}$/.test(symbol)) {
      return NextResponse.json({ error: 'invalid' }, { status: 400 });
    }

    // ── IP throttle ──────────────────────────────────────────────────────────
    const ip  = getIp(req);
    const now = Date.now();
    const entry = ipMap.get(ip);
    if (entry && now - entry.windowStart < WINDOW_MS) {
      if (entry.count >= MAX_WRITES) {
        return NextResponse.json({ error: 'rate limited' }, { status: 429 });
      }
      entry.count++;
    } else {
      // First request in this window (or window expired) — open a new window.
      ipMap.set(ip, { windowStart: now, count: 1 });
    }

    await prisma.searchLog.create({ data: { tickerSymbol: symbol } });

    return NextResponse.json({ ok: true });
  } catch {
    // Non-critical — never surface logging errors to the client
    return NextResponse.json({ ok: false }, { status: 500 });
  }
}
