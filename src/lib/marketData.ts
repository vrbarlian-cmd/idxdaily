/**
 * Yahoo Finance market data fetcher.
 *
 * Historical functions THROW on failure — callers must catch and treat the
 * component as unavailable. Never silently return zeros or 50s.
 *
 * Foreign net flow is always null until we integrate idx.co.id scraping.
 */

export interface DailyBar {
  date: string;    // YYYY-MM-DD
  close: number;
  volume?: number;
}

export interface MarketSnapshot {
  ihsgValue: number | null;
  ihsgChangePercent: number | null;
  usdIdr: number | null;
  foreignFlowIdr: null; // TODO: scrape from idx.co.id/market-data/reports/foreign-transaction
}

// ── Cache store ──────────────────────────────────────────────────────────────

const HISTORY_TTL_MS  = 30 * 60 * 1000;  // 30 min
const SNAPSHOT_TTL_MS =  5 * 60 * 1000;  //  5 min

let _ihsgCache:     { data: DailyBar[];     ts: number } | null = null;
let _usdIdrCache:   { data: DailyBar[];     ts: number } | null = null;
let _snapshotCache: { data: MarketSnapshot; ts: number } | null = null;

// ── Low-level fetch ──────────────────────────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function yahooChart(ticker: string, range: string): Promise<any> {
  const url =
    `https://query1.finance.yahoo.com/v8/finance/chart/` +
    `${encodeURIComponent(ticker)}?range=${range}&interval=1d`;

  const res = await fetch(url, {
    headers: { 'User-Agent': 'Mozilla/5.0' },
    next: { revalidate: 1800 },
  });

  if (!res.ok) throw new Error(`Yahoo Finance ${ticker}: HTTP ${res.status}`);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const json = await res.json() as any;
  const result = json?.chart?.result?.[0];
  if (!result) throw new Error(`Yahoo Finance ${ticker}: no chart result in response`);
  return result;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function parseBars(result: any): DailyBar[] {
  const timestamps: number[] = result.timestamp ?? [];
  const closes: number[]     = result.indicators?.quote?.[0]?.close ?? [];
  const volumes: number[]    = result.indicators?.quote?.[0]?.volume ?? [];

  const bars: DailyBar[] = [];
  for (let i = 0; i < timestamps.length; i++) {
    if (closes[i] == null || isNaN(closes[i])) continue;
    bars.push({
      date:   new Date(timestamps[i] * 1000).toISOString().slice(0, 10),
      close:  closes[i],
      volume: volumes[i] ?? undefined,
    });
  }
  return bars;
}

// ── Public history fetchers ──────────────────────────────────────────────────

/**
 * ~250 trading days of IHSG daily closes (1-year range from Yahoo).
 * Throws if Yahoo returns insufficient data or fails entirely.
 */
export async function fetchIhsgHistory(): Promise<DailyBar[]> {
  if (_ihsgCache && Date.now() - _ihsgCache.ts < HISTORY_TTL_MS) return _ihsgCache.data;

  const result = await yahooChart('^JKSE', '1y');
  const bars   = parseBars(result);

  if (bars.length < 50) {
    throw new Error(`IHSG: only ${bars.length} bars returned — Yahoo may be throttling`);
  }

  _ihsgCache = { data: bars, ts: Date.now() };
  return bars;
}

/**
 * ~250 trading days of USD/IDR daily closes (1-year range from Yahoo).
 * Throws if Yahoo returns insufficient data or fails entirely.
 * Note: IDR=X in Yahoo is USD/IDR (1 USD = N IDR). Higher = weaker rupiah.
 */
export async function fetchUsdIdrHistory(): Promise<DailyBar[]> {
  if (_usdIdrCache && Date.now() - _usdIdrCache.ts < HISTORY_TTL_MS) return _usdIdrCache.data;

  const result = await yahooChart('IDR=X', '1y');
  const bars   = parseBars(result);

  if (bars.length < 30) {
    throw new Error(`USD/IDR: only ${bars.length} bars returned`);
  }

  _usdIdrCache = { data: bars, ts: Date.now() };
  return bars;
}

// ── Live snapshot (derived from history cache) ───────────────────────────────

export async function fetchMarketSnapshot(): Promise<MarketSnapshot> {
  if (_snapshotCache && Date.now() - _snapshotCache.ts < SNAPSHOT_TTL_MS) return _snapshotCache.data;

  const [ihsg, usd] = await Promise.allSettled([fetchIhsgHistory(), fetchUsdIdrHistory()]);

  const ihsgBars = ihsg.status === 'fulfilled' ? ihsg.value : [];
  const usdBars  = usd.status  === 'fulfilled' ? usd.value  : [];

  const lastClose = (arr: DailyBar[]) => arr.at(-1)?.close ?? null;
  const prevClose = (arr: DailyBar[]) => arr.at(-2)?.close ?? null;
  const chgPct = (cur: number | null, pre: number | null) =>
    cur != null && pre != null ? ((cur - pre) / pre) * 100 : null;

  const data: MarketSnapshot = {
    ihsgValue:         lastClose(ihsgBars),
    ihsgChangePercent: chgPct(lastClose(ihsgBars), prevClose(ihsgBars)),
    usdIdr:            lastClose(usdBars),
    foreignFlowIdr:    null,
  };

  _snapshotCache = { data, ts: Date.now() };
  return data;
}
