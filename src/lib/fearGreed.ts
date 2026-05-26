/**
 * IDX Fear & Greed Index — percentile-rank formula.
 *
 * Each component is scored 0–100 relative to its own recent history
 * (CNN / CoinMarketCap methodology). Missing components are EXCLUDED
 * from the aggregate and weights are renormalized — never defaulted to 50.
 *
 * Requires ≥2 active components to produce a score; otherwise returns null.
 */

import { prisma } from './prisma';
import { fetchIhsgHistory, fetchUsdIdrHistory } from './marketData';
import type { DailyBar } from './marketData';

// ── Types ────────────────────────────────────────────────────────────────────

export interface ComponentResult {
  id:          string;
  label:       string;
  weight:      number;         // nominal weight  0–1
  score:       number | null;  // 0–100 percentile; null = unavailable
  status:      'active' | 'stale' | 'unavailable';
  raw:         number | null;  // underlying metric value
  rawLabel:    string | null;  // human-readable context, e.g. "−3.24% vs MA125"
  note:        string | null;  // warning / explanation shown in UI
}

export interface FearGreedData {
  // Index
  score:            number | null;  // SMOOTHED score (display value)
  rawScore:         number | null;  // unsmoothed weighted average
  label:            string;
  // Article sentiment (for gauge bars — independent of market data)
  bullishPct:       number;
  bearishPct:       number;
  neutralPct:       number;
  articleCount:     number;
  enrichedCount:    number;
  days:             number;
  insufficient:     boolean;        // true when score === null
  // Components
  components:       ComponentResult[];
  activeComponents: number;
}

// ── Math helpers ─────────────────────────────────────────────────────────────

/**
 * Returns 0–100: fraction of history values strictly below `value`.
 * Higher = value is near the top of its historical range (greed).
 */
function percentileRank(value: number, history: number[]): number {
  if (!history.length) return 50;
  const below = history.filter(h => h < value).length;
  return (below / history.length) * 100;
}

function rollingMean(arr: number[], endIdx: number, window: number): number | null {
  if (endIdx < window - 1) return null;
  let sum = 0;
  for (let i = endIdx - window + 1; i <= endIdx; i++) sum += arr[i];
  return sum / window;
}

function rollingStdDev(arr: number[], endIdx: number, window: number): number | null {
  if (endIdx < window - 1) return null;
  const slice = arr.slice(endIdx - window + 1, endIdx + 1);
  const mean  = slice.reduce((a, b) => a + b, 0) / slice.length;
  return Math.sqrt(slice.reduce((s, v) => s + (v - mean) ** 2, 0) / slice.length);
}

function round1(n: number) { return Math.round(n * 10) / 10; }
function fmtPct(n: number)  { return (n >= 0 ? '+' : '') + n.toFixed(2) + '%'; }

// ── Component computers (pure, synchronous for market data) ──────────────────

/**
 * Component 1 — IHSG Momentum (weight 20%)
 * Score = percentile rank of (current / MA125 − 1) vs all available history.
 * Higher deviation above MA = more greed.
 */
function computeIhsgMomentum(bars: DailyBar[]): ComponentResult {
  const MA_WIN = 125;
  const closes = bars.map(b => b.close);

  if (closes.length < MA_WIN + 5) {
    return {
      id: 'ihsg_momentum', label: 'IHSG Momentum', weight: 0.20,
      score: null, status: 'unavailable', raw: null, rawLabel: null,
      note: `Perlu ≥${MA_WIN + 5} hari data IHSG`,
    };
  }

  const devs: number[] = [];
  for (let i = MA_WIN - 1; i < closes.length; i++) {
    devs.push(closes[i] / rollingMean(closes, i, MA_WIN)! - 1);
  }

  const current = devs.at(-1)!;
  const history = devs.slice(0, -1);
  const score   = percentileRank(current, history);

  return {
    id: 'ihsg_momentum', label: 'IHSG Momentum', weight: 0.20,
    score:    round1(score),
    status:   'active',
    raw:      current,
    rawLabel: `IHSG ${fmtPct(current * 100)} vs MA${MA_WIN}`,
    note:     null,
  };
}

/**
 * Component 2 — IHSG Volatility (weight 15%)
 * Score = 100 − percentile of 20-day annualized vol vs history.
 * High volatility = fear = low score.
 */
function computeIhsgVolatility(bars: DailyBar[]): ComponentResult {
  const VOL_WIN  = 20;
  const MIN_BARS = 40;
  const closes   = bars.map(b => b.close);

  if (closes.length < MIN_BARS) {
    return {
      id: 'ihsg_volatility', label: 'Volatilitas IHSG', weight: 0.15,
      score: null, status: 'unavailable', raw: null, rawLabel: null,
      note: `Perlu ≥${MIN_BARS} hari data`,
    };
  }

  const logRets: number[] = [];
  for (let i = 1; i < closes.length; i++) logRets.push(Math.log(closes[i] / closes[i - 1]));

  const vols: number[] = [];
  for (let i = VOL_WIN - 1; i < logRets.length; i++) {
    vols.push(rollingStdDev(logRets, i, VOL_WIN)! * Math.sqrt(252));
  }

  const current = vols.at(-1)!;
  const history = vols.slice(0, -1);
  const score   = 100 - percentileRank(current, history);

  return {
    id: 'ihsg_volatility', label: 'Volatilitas IHSG', weight: 0.15,
    score:    round1(score),
    status:   'active',
    raw:      current,
    rawLabel: `Vol ${(current * 100).toFixed(1)}% (ann.)`,
    note:     null,
  };
}

/**
 * Component 3 — Foreign Net Flow (weight 20%)
 * Manually entered daily via set_foreign_flow.py after market close.
 * Uses 5-day rolling sum percentile-ranked vs history (≥2 rows to activate).
 */
async function computeForeignFlow(): Promise<ComponentResult> {
  const ROLL_WIN = 5;
  const MIN_ROWS = 2;
  const cutoff90 = new Date(Date.now() - 90 * 24 * 60 * 60 * 1000);

  const rows = await prisma.$queryRaw<Array<{ net_idr_billions: number | null }>>`
    SELECT net_idr_billions
    FROM foreign_flow_daily
    WHERE date >= ${cutoff90} AND net_idr_billions IS NOT NULL
    ORDER BY date ASC
  `;

  if (rows.length < MIN_ROWS) {
    const n = rows.length;
    return {
      id: 'foreign_flow', label: 'Aliran Asing', weight: 0.20,
      score: null, status: 'unavailable', raw: null, rawLabel: null,
      note: n === 0
        ? 'Diperbarui manual setiap hari setelah penutupan pasar.'
        : `Baru ${n} hari data — butuh min ${MIN_ROWS} untuk aktif`,
    };
  }

  const nets = rows.map(r => r.net_idr_billions as number);

  // 5-day rolling sum at each position
  const rollSums = nets.map((_, i) => {
    const win = nets.slice(Math.max(0, i - ROLL_WIN + 1), i + 1);
    return win.reduce((a: number, b: number) => a + b, 0);
  });

  const current = rollSums.at(-1)!;
  const history = rollSums.slice(0, -1);

  const score = history.length > 0 ? percentileRank(current, history) : 50;
  const sign  = current >= 0 ? '+' : '';

  return {
    id: 'foreign_flow', label: 'Aliran Asing', weight: 0.20,
    score:    round1(score),
    status:   'active',
    raw:      current,
    rawLabel: `5d net ${sign}${current.toFixed(0)} Rp miliar (p${score.toFixed(0)}, ${rows.length} hari data)`,
    note:     null,
  };
}

/**
 * Component 4 — Rupiah Stress / USD/IDR Pressure (weight 15%)
 * Score = 100 − percentile of (current / MA50 − 1) vs history.
 * Rupiah weakness above 50d MA = fear = low score.
 */
function computeRupiahStress(bars: DailyBar[]): ComponentResult {
  const MA_WIN = 50;
  const closes = bars.map(b => b.close);

  if (closes.length < MA_WIN + 1) {
    return {
      id: 'rupiah_stress', label: 'Tekanan Rupiah', weight: 0.15,
      score: null, status: 'unavailable', raw: null, rawLabel: null,
      note: `Perlu ≥${MA_WIN + 1} hari data USD/IDR`,
    };
  }

  const devs: number[] = [];
  for (let i = MA_WIN - 1; i < closes.length; i++) {
    devs.push(closes[i] / rollingMean(closes, i, MA_WIN)! - 1);
  }

  const current   = devs.at(-1)!;
  const history   = devs.slice(0, -1);
  const pct       = history.length > 0 ? percentileRank(current, history) : 50;
  const score     = 100 - pct;
  const lastClose = closes.at(-1)!;

  return {
    id: 'rupiah_stress', label: 'Tekanan Rupiah', weight: 0.15,
    score:    round1(score),
    status:   history.length >= 30 ? 'active' : 'stale',
    raw:      lastClose,
    rawLabel: `USD/IDR ${Math.round(lastClose).toLocaleString('id-ID')} (${fmtPct(current * 100)} vs MA${MA_WIN})`,
    note:     history.length < 30
      ? 'Riwayat terbatas — peringkat persentil kurang akurat'
      : null,
  };
}

/**
 * Component 5 — Headline Sentiment (weight 20%)
 * 3-day exponentially-weighted: last 24h weight 1.0 | 24-48h weight 0.4.
 * Requires ≥10 enriched articles in the last 24h to be active.
 * Reduces single-day whipsaws without lagging too far behind.
 */
async function computeHeadlineSentiment(): Promise<ComponentResult> {
  const MIN_ENRICHED_24H = 10;
  const now      = Date.now();
  const cutoff48h = new Date(now - 48 * 60 * 60 * 1000);
  const cutoff24h = new Date(now - 24 * 60 * 60 * 1000);

  const rows = await prisma.news.findMany({
    where:  { publishedAt: { gte: cutoff48h } },
    select: { sentiment: true, aiSummary: true, publishedAt: true },
  });

  const enriched24h = rows.filter(r => r.aiSummary && r.publishedAt && r.publishedAt >= cutoff24h);
  const total24h    = rows.filter(r => r.publishedAt && r.publishedAt >= cutoff24h);
  const n24         = enriched24h.length;

  if (n24 < MIN_ENRICHED_24H) {
    return {
      id: 'headline_sentiment', label: 'Sentimen Headline', weight: 0.20,
      score: null, status: 'unavailable', raw: null, rawLabel: null,
      note: `Hanya ${n24}/${total24h.length} artikel terenrichment dalam 24h (min ${MIN_ENRICHED_24H})`,
    };
  }

  // Weighted score: 24h-old articles count as 40% of recent
  let wBull = 0, wBear = 0, totalW = 0;
  for (const r of rows) {
    if (!r.aiSummary || !r.publishedAt) continue;
    const w = r.publishedAt >= cutoff24h ? 1.0 : 0.4;
    if (r.sentiment === 'BULLISH') wBull += w;
    else if (r.sentiment === 'BEARISH') wBear += w;
    totalW += w;
  }

  const score     = totalW > 0 ? round1(50 + ((wBull - wBear) / totalW) * 50) : 50;
  const enrichPct = Math.round((n24 / Math.max(total24h.length, 1)) * 100);
  const bull24    = enriched24h.filter(r => r.sentiment === 'BULLISH').length;
  const bear24    = enriched24h.filter(r => r.sentiment === 'BEARISH').length;

  return {
    id: 'headline_sentiment', label: 'Sentimen Headline', weight: 0.20,
    score,
    status:   enrichPct >= 30 ? 'active' : 'stale',
    raw:      score,
    rawLabel: `${bull24}B / ${bear24}Be / ${n24 - bull24 - bear24}N (24h, bobot 48h)`,
    note:     enrichPct < 30
      ? `Hanya ${n24}/${total24h.length} artikel terenrichment — sinyal kurang akurat`
      : null,
  };
}

/**
 * Component 6 — Market Breadth (weight 10%)
 * Deprioritized — will be enabled once the 5-component index is stable.
 */
async function computeMarketBreadth(): Promise<ComponentResult> {
  return {
    id: 'breadth', label: 'Market Breadth', weight: 0.10,
    score: null, status: 'unavailable', raw: null, rawLabel: null,
    note: 'Market breadth — segera hadir',
  };
}

// ── Aggregation ──────────────────────────────────────────────────────────────

function classify(score: number): string {
  if (score < 25) return 'Extreme Fear';
  if (score < 45) return 'Fear';
  if (score < 55) return 'Neutral';
  if (score < 75) return 'Greed';
  return 'Extreme Greed';
}

function aggregate(components: ComponentResult[]): {
  score: number | null;
  label: string;
  activeCount: number;
} {
  const active = components.filter(c => c.score !== null);

  if (active.length < 2) {
    return { score: null, label: 'Data Tidak Cukup', activeCount: active.length };
  }

  const totalW   = active.reduce((s, c) => s + c.weight, 0);
  const weighted = active.reduce((s, c) => s + c.score! * c.weight, 0);
  const score    = round1(weighted / totalW);

  return { score, label: classify(score), activeCount: active.length };
}

// ── Public API ───────────────────────────────────────────────────────────────

export async function computeFearGreed(days = 7): Promise<FearGreedData> {
  const cutoff = new Date(Date.now() - days * 24 * 60 * 60 * 1000);

  const unavailable = (id: string, label: string, weight: number, note: string): ComponentResult => ({
    id, label, weight, score: null, status: 'unavailable', raw: null, rawLabel: null, note,
  });

  // Fetch all data sources in parallel
  const [ihsgRes, usdIdrRes, articleRes, headlineRes, foreignRes, breadthRes] =
    await Promise.allSettled([
      fetchIhsgHistory(),
      fetchUsdIdrHistory(),
      prisma.news.findMany({
        where:  { publishedAt: { gte: cutoff } },
        select: { sentiment: true, aiSummary: true },
      }),
      computeHeadlineSentiment(),
      computeForeignFlow(),
      computeMarketBreadth(),
    ]);

  const ihsgBars   = ihsgRes.status   === 'fulfilled' ? ihsgRes.value   : null;
  const usdIdrBars = usdIdrRes.status === 'fulfilled' ? usdIdrRes.value : null;
  const articles   = articleRes.status === 'fulfilled' ? articleRes.value : [];
  const headline   = headlineRes.status === 'fulfilled' ? headlineRes.value
    : unavailable('headline_sentiment', 'Sentimen Headline', 0.20, 'Gagal mengambil data artikel');
  const foreignFlow = foreignRes.status === 'fulfilled' ? foreignRes.value
    : unavailable('foreign_flow', 'Aliran Asing', 0.20, 'Gagal membaca data aliran asing');
  const breadth     = breadthRes.status === 'fulfilled' ? breadthRes.value
    : unavailable('breadth', 'Market Breadth', 0.10, 'Gagal membaca data LQ45 — jalankan sync_breadth.py');

  // Article stats for gauge bars
  const n             = articles.length;
  const enrichedCount = articles.filter(a => a.aiSummary !== null).length;
  const bullN         = articles.filter(a => a.sentiment === 'BULLISH').length;
  const bearN         = articles.filter(a => a.sentiment === 'BEARISH').length;
  const neutN         = n - bullN - bearN;

  const components: ComponentResult[] = [
    ihsgBars
      ? computeIhsgMomentum(ihsgBars)
      : unavailable('ihsg_momentum', 'IHSG Momentum', 0.20, 'Gagal mengambil data IHSG dari Yahoo Finance'),
    ihsgBars
      ? computeIhsgVolatility(ihsgBars)
      : unavailable('ihsg_volatility', 'Volatilitas IHSG', 0.15, 'Gagal mengambil data IHSG dari Yahoo Finance'),
    foreignFlow,
    usdIdrBars
      ? computeRupiahStress(usdIdrBars)
      : unavailable('rupiah_stress', 'Tekanan Rupiah', 0.15, 'Gagal mengambil data USD/IDR dari Yahoo Finance'),
    headline,
    breadth,
  ];

  // Raw aggregate
  const { score: rawScore, label, activeCount } = aggregate(components);

  // EMA smoothing: read yesterday's smoothed score from DB (alpha = 0.7)
  const EMA_ALPHA = 0.7;
  let smoothedScore: number | null = null;
  let prevSmoothed: number | null  = null;
  try {
    const prev = await prisma.$queryRaw<Array<{ smoothed_score: number | null }>>`
      SELECT smoothed_score FROM fear_greed_index
      WHERE date < CURRENT_DATE AND smoothed_score IS NOT NULL
      ORDER BY date DESC LIMIT 1
    `;
    prevSmoothed = prev[0]?.smoothed_score ?? null;
  } catch { /* first run — no prior smoothed */ }

  if (rawScore !== null) {
    smoothedScore = prevSmoothed !== null
      ? round1(EMA_ALPHA * rawScore + (1 - EMA_ALPHA) * prevSmoothed)
      : rawScore;
  } else {
    smoothedScore = prevSmoothed;   // carry forward
  }

  const displayScore = smoothedScore;
  const displayLabel = displayScore !== null ? (
    rawScore !== null ? label : classify(displayScore)
  ) : 'Data Tidak Cukup';

  return {
    score:            displayScore,
    rawScore,
    label:            displayLabel,
    bullishPct:       n > 0 ? round1((bullN / n) * 100) : 0,
    bearishPct:       n > 0 ? round1((bearN / n) * 100) : 0,
    neutralPct:       n > 0 ? round1((neutN / n) * 100) : 0,
    articleCount:     n,
    enrichedCount,
    days,
    insufficient:     displayScore === null,
    components,
    activeComponents: activeCount,
  };
}

// Keep the old interface alias for backward compat with gauge
export type { FearGreedData as FearGreedResult };

// ── Historical values ────────────────────────────────────────────────────────

export interface HistoricalEntry {
  value: number | null;
  label: string;           // classify label or 'no_data'
}

export interface HistoricalValues {
  now:       HistoricalEntry;
  yesterday: HistoricalEntry;
  lastWeek:  HistoricalEntry;
  lastMonth: HistoricalEntry;
}

const NO_HIST: HistoricalEntry = { value: null, label: 'no_data' };

/**
 * Reads fear_greed_index rows and returns the closest entry to each
 * historical milestone (now / yesterday / last week / last month).
 *
 * Single source of truth: uses `smoothed_score` exclusively.
 * Excludes:
 *   - corrupt legacy rows (smoothed_score IS NULL)  ← THIS is what caused the "98" bug
 *
 * Backfilled rows ARE included for Last Week / Last Month slots — they use
 * the same clean smoothed series the chart displays (dashed line).  The "Now"
 * slot is anchored to the most-recent live row (is_backfilled = FALSE) so the
 * gauge and chart "saat ini" always show a live-computed figure.
 */
export async function getHistoricalValues(): Promise<HistoricalValues> {
  // Fetch up to 90 most-recent non-corrupt rows (live + backfilled)
  // The only hard exclusion: smoothed_score IS NULL (corrupt/incomplete rows)
  const rows = await prisma.$queryRaw<
    Array<{ date: Date; smoothed_score: number | null; label: string; is_backfilled: boolean | null }>
  >`SELECT date, smoothed_score, label, is_backfilled
    FROM fear_greed_index
    WHERE smoothed_score IS NOT NULL
    ORDER BY date DESC
    LIMIT 90`;

  if (!rows.length) return { now: NO_HIST, yesterday: NO_HIST, lastWeek: NO_HIST, lastMonth: NO_HIST };

  // "Now" = most-recent LIVE (non-backfilled) row — anchors the gauge/chart "saat ini"
  // Falls back to most-recent backfilled if no live row exists (edge case: first day).
  const liveRows = rows.filter(r => !r.is_backfilled);
  const nowRow   = liveRows[0] ?? rows[0];
  const now: HistoricalEntry = { value: nowRow.smoothed_score, label: nowRow.label };

  const todayMidnight = new Date();
  todayMidnight.setHours(0, 0, 0, 0);

  const findNearest = (daysAgo: number, toleranceDays = 4): HistoricalEntry => {
    const targetMs = todayMidnight.getTime() - daysAgo * 86_400_000;
    let best: (typeof rows)[0] | null = null;
    let bestDiff = Infinity;

    for (const row of rows) {
      const rowMs = row.date instanceof Date
        ? row.date.getTime()
        : new Date(row.date as unknown as string).getTime();

      // Exclude today's row when looking for "yesterday" or further
      if (daysAgo >= 1 && rowMs >= todayMidnight.getTime()) continue;

      const diff = Math.abs(rowMs - targetMs);
      if (diff < bestDiff) { bestDiff = diff; best = row; }
    }

    if (!best || bestDiff > toleranceDays * 86_400_000) return NO_HIST;
    return { value: best.smoothed_score, label: best.label };
  };

  return {
    now,
    yesterday: findNearest(1, 2),
    lastWeek:  findNearest(7, 4),
    lastMonth: findNearest(30, 5),
  };
}
