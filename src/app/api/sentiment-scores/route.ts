import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export const dynamic = 'force-dynamic';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface ScoreEntry {
  score:  number | null;
  label:  string;
  date:   string | null;
}

export interface DivergenceInfo {
  magnitude:    number;
  signal:       string;   // 'ritel_euforia' | 'asing_optimis'
  message:      string;   // OJK-safe Bahasa Indonesia message
}

export interface SentimentScoresResponse {
  overall:    ScoreEntry & { foreignWeight: number; domesticWeight: number; hasDomesticData: boolean };
  foreign:    ScoreEntry;
  domestic:   ScoreEntry & {
    hasDomesticData:       boolean;
    daysOfData:            number;
    participationRatio:    number | null;
    participationMode:     'market_share' | 'self_normalized' | null;
    marketDirectionScore:  number | null;
  };
  divergence: DivergenceInfo | null;
}

// ── GET /api/sentiment-scores ─────────────────────────────────────────────────

export async function GET() {
  // Fetch all three in parallel
  const [overallRows, foreignRows, domesticRows] = await Promise.all([

    prisma.$queryRaw<Array<{
      date:                Date;
      smoothed_score:      number | null;
      label:               string;
      foreign_score:       number | null;
      domestic_score:      number | null;
      foreign_weight:      number;
      domestic_weight:     number;
      has_domestic_data:   boolean;
      divergence_magnitude: number | null;
      divergence_signal:   string | null;
    }>>`
      SELECT date, smoothed_score, label,
             foreign_score, domestic_score,
             foreign_weight, domestic_weight, has_domestic_data,
             divergence_magnitude, divergence_signal
      FROM overall_sentiment_daily
      ORDER BY date DESC LIMIT 1
    `,

    prisma.$queryRaw<Array<{
      date:           Date;
      smoothed_score: number | null;
      label:          string;
    }>>`
      SELECT date, smoothed_score, label
      FROM fear_greed_index
      ORDER BY date DESC LIMIT 1
    `,

    prisma.$queryRaw<Array<{
      date:                           Date;
      smoothed_score:                 number | null;
      label:                          string;
      has_retail_data:                boolean;
      days_of_retail_data:            number | null;
      retail_participation_ratio:     number | null;
      participation_uses_total_market: boolean | null;
      market_direction_score:         number | null;
    }>>`
      SELECT date, smoothed_score, label,
             has_retail_data, days_of_retail_data,
             retail_participation_ratio,
             participation_uses_total_market,
             market_direction_score
      FROM fear_greed_psychology
      ORDER BY date DESC LIMIT 1
    `,
  ]);

  // ── Foreign Score ────────────────────────────────────────────────────────────
  const fg = foreignRows[0] ?? null;
  const foreign: ScoreEntry = {
    score: fg?.smoothed_score != null ? Number(fg.smoothed_score) : null,
    label: fg?.label ?? 'Data Tidak Cukup',
    date:  fg?.date ? (fg.date instanceof Date ? fg.date.toISOString().slice(0, 10) : String(fg.date).slice(0, 10)) : null,
  };

  // ── Domestic Score ───────────────────────────────────────────────────────────
  const dom = domesticRows[0] ?? null;
  const domDate = dom?.date
    ? (dom.date instanceof Date ? dom.date.toISOString().slice(0, 10) : String(dom.date).slice(0, 10))
    : null;

  const domestic = {
    score:  dom?.smoothed_score != null ? Number(dom.smoothed_score) : null,
    label:  dom?.label ?? 'Data Tidak Cukup',
    date:   domDate,
    hasDomesticData:       Boolean(dom?.has_retail_data),
    daysOfData:            dom?.days_of_retail_data != null ? Number(dom.days_of_retail_data) : 0,
    participationRatio:    dom?.retail_participation_ratio != null ? Number(dom.retail_participation_ratio) : null,
    participationMode:     (dom?.participation_uses_total_market === true
                            ? 'market_share'
                            : dom?.participation_uses_total_market === false && dom?.has_retail_data
                            ? 'self_normalized'
                            : null) as 'market_share' | 'self_normalized' | null,
    marketDirectionScore:  dom?.market_direction_score != null ? Number(dom.market_direction_score) : null,
  };

  // ── Overall Score ────────────────────────────────────────────────────────────
  const ov = overallRows[0] ?? null;
  const ovDate = ov?.date
    ? (ov.date instanceof Date ? ov.date.toISOString().slice(0, 10) : String(ov.date).slice(0, 10))
    : null;

  const overall = {
    score:           ov?.smoothed_score != null ? Number(ov.smoothed_score) : foreign.score,
    label:           ov?.label ?? foreign.label,
    date:            ovDate,
    foreignWeight:   ov?.foreign_weight != null ? Number(ov.foreign_weight) : 0.6,
    domesticWeight:  ov?.domestic_weight != null ? Number(ov.domestic_weight) : 0.4,
    hasDomesticData: Boolean(ov?.has_domestic_data),
  };

  // ── Divergence ───────────────────────────────────────────────────────────────
  let divergence: DivergenceInfo | null = null;
  if (ov?.divergence_signal && ov.divergence_magnitude != null) {
    divergence = {
      magnitude: Number(ov.divergence_magnitude),
      signal:    ov.divergence_signal,
      message:   getDivergenceMessage(ov.divergence_signal),
    };
  }

  const response: SentimentScoresResponse = {
    overall,
    foreign,
    domestic,
    divergence,
  };

  return NextResponse.json(response);
}

// ── Divergence message lookup ─────────────────────────────────────────────────
// Full messages stored here (worker stores only the signal key)

function getDivergenceMessage(signal: string): string {
  switch (signal) {
    case 'ritel_euforia':
      return 'Ritel aktif saat asing berhati-hati — waspadai potensi koreksi. Ini adalah sinyal sentimen, bukan rekomendasi jual/beli.';
    case 'asing_optimis':
      return 'Asing lebih optimis daripada ritel — waspadai potensi pemulihan. Ini adalah sinyal sentimen, bukan rekomendasi jual/beli.';
    default:
      return 'Sentimen asing dan ritel menunjukkan arah yang berbeda.';
  }
}
