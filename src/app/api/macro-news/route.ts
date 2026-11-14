import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export const revalidate = 60;

// ── Berita Makro & Pasar selection ───────────────────────────────────────────
// Goal: the 8 most important market-moving stories right now, one per topic.
//   1. Candidates  — enriched articles from the last WINDOW_HOURS that either
//                    hit a market topic (MSCI, Fed, oil, …) or pass the old
//                    category/impact rules.
//   2. Ranking     — impact score + topic boost − age penalty, with a penalty
//                    for company-specific headlines.
//   3. Diversity   — max 1 article per topic (untopic'd items share one slot), plus
//                    word-overlap dedup, so the section never repeats a story.

const WINDOW_HOURS = 72;
const MAX_ARTICLES = 8;

const GLOBAL_SOURCES = [
  'Bloomberg Markets', 'CNBC International', 'Investing.com', 'Federal Reserve',
];

const MACRO_ACRONYMS = new Set([
  'BI', 'OJK', 'BEI', 'LPS', 'KSSK',
  'IHSG', 'LQ45', 'IDX', 'IDR', 'USD', 'EUR', 'JPY', 'CNY', 'SGD',
  'US', 'EU', 'UK', 'IMF', 'WTO', 'OPEC', 'G20', 'G7',
  'Fed', 'ECB', 'BOJ', 'RBI',
  'MSCI', 'FTSE', 'DJIA', 'SPX', 'DXY',
  'GDP', 'PMI', 'CPI', 'PPI', 'SBN', 'ETF', 'IPO',
  'APBN', 'APBD', 'PPN', 'PPh', 'BUMN', 'PNBP',
]);

// Ordered by priority: an article belongs to the FIRST topic it matches.
// `boost` lifts topics the owner wants captured whenever they are happening.
// `allowCompany` lets ticker-tagged / DISCLOSURE articles in (index reviews
// always name stocks, but the story itself is market-wide).
interface Topic { id: string; re: RegExp; boost: number; allowCompany?: boolean }

const TOPICS: Topic[] = [
  { id: 'index-review', re: /\b(msci|ftse|russell)\b/i,                                         boost: 2.5, allowCompany: true },
  { id: 'sov-rating',   re: /\b(fitch|moody'?s|s&p global|pefindo|r&i|jcr)\b.*\b(indonesia|ri|sovereign|negara|pemerintah)\b|\b(rating|peringkat|outlook)\s+(utang\s+)?(indonesia|ri)\b/i, boost: 2.5, allowCompany: true },
  { id: 'fed',          re: /\b(the fed|fed|fomc|powell|federal reserve|suku bunga as)\b/i,      boost: 2.0 },
  { id: 'bi',           re: /\b([Bb]ank [Ii]ndonesia|BI[- ][Rr]ate|RDG BI|BI)\b/,                boost: 2.0 },
  { id: 'boj-ecb',      re: /\b(boj|bank of japan|bank sentral jepang|ecb|yen)\b/i,               boost: 1.5 },
  { id: 'geopolitics',  re: /\b(perang|war|iran|israel|ukraina|ukraine|rusia|russia|geopolitik|geopolitical|serangan)\b/i, boost: 1.5 },
  { id: 'oil',          re: /\b(minyak|oil|brent|wti|opec)\b/i,                                   boost: 1.5 },
  { id: 'gold',         re: /\b(emas|gold)\b/i,                                                   boost: 1.0 },
  { id: 'us-stocks',    re: /\b(wall street|s&p 500|nasdaq|dow jones|saham as|bursa as|us stocks)\b/i, boost: 1.5 },
  { id: 'big-ipo',      re: /\b(anthropic|openai|spacex)\b/i,                                     boost: 1.5 },
  { id: 'rupiah',       re: /\b(rupiah|kurs|usd\/idr|idr\/usd)\b/i,                               boost: 1.0 },
  { id: 'ihsg',         re: /\b(ihsg)\b/i,                                                        boost: 0.5 },
  { id: 'china',        re: /\b(china|tiongkok|beijing)\b/i,                                      boost: 1.0 },
  { id: 'macro-data',   re: /\b(inflasi|inflation|cpi|pdb|gdp|neraca perdagangan|pmi|apbn|defisit)\b/i, boost: 1.0 },
];

// Index reviews / sovereign ratings win outright (their headlines often lead
// with IHSG or a ticker). Otherwise the topic mentioned EARLIEST in the
// headline is the story's subject: "Wall Street Menguat … The Fed" → us-stocks.
function topicOf(title: string): Topic | null {
  const priority = TOPICS.find(t => t.allowCompany && t.re.test(title));
  if (priority) return priority;
  let best: Topic | null = null;
  let bestPos = Infinity;
  for (const t of TOPICS) {
    const pos = title.search(t.re);
    if (pos >= 0 && pos < bestPos) { best = t; bestPos = pos; }
  }
  return best;
}

function looksCompanySpecific(title: string): boolean {
  if (/^saham[\s-]/i.test(title)) return true;
  if (/\bemiten\s+[A-Z]{2,5}\b/i.test(title)) return true;
  if (/\bdividen\b/i.test(title)) return true;
  if (/^(laba|rugi|pendapatan)\s+[A-Z]{2,5}\b/i.test(title)) return true;
  const leadWord = title.match(/^([A-Z]{2,5})(?=[\s:])/)?.[1];
  if (leadWord && !MACRO_ACRONYMS.has(leadWord)) return true;
  return false;
}

// Old category/impact rules — still admit untopic'd macro stories.
function passesCategoryRules(a: { source: string; category: string; impactScore: number; tickerId: string | null }): boolean {
  if (GLOBAL_SOURCES.includes(a.source)) return a.impactScore >= 4.5;
  if (a.tickerId) return false;
  if (a.category === 'MACRO' || a.category === 'REGULATORY') return a.impactScore >= 5.5;
  if (a.category === 'SECTOR') return a.impactScore >= 7.0;
  if (a.category === 'FINANCIAL') return a.impactScore >= 4.5;
  return false;
}

function significantWords(title: string): Set<string> {
  return new Set(title.toLowerCase().split(/\s+/).filter(w => w.length > 3));
}

// ── GET /api/macro-news ───────────────────────────────────────────────────────

export async function GET() {
  const since = new Date(Date.now() - WINDOW_HOURS * 3600_000);

  const raw = await prisma.news.findMany({
    where: {
      aiSummary:   { not: null },
      category:    { not: 'SKIP' },
      publishedAt: { gte: since },
    },
    orderBy: { publishedAt: 'desc' },
    take: 1500,
    select: {
      id: true, title: true, aiSummary: true, url: true, source: true,
      publishedAt: true, sentiment: true, impactScore: true, category: true,
      tickerId: true,
      ticker: { select: { symbol: true } },
    },
  });

  const now = Date.now();
  const scored = raw.flatMap(a => {
    const topic   = topicOf(a.title);
    const company = !!a.tickerId || looksCompanySpecific(a.title) || a.category === 'DISCLOSURE' || a.category === 'CORPORATE';

    let eligible: boolean;
    if (topic) {
      const minImpact = GLOBAL_SOURCES.includes(a.source) ? 4.5 : 4.0;
      eligible = a.impactScore >= minImpact && (!company || !!topic.allowCompany);
    } else {
      eligible = !company && passesCategoryRules(a);
    }
    if (!eligible) return [];

    const ageHours = a.publishedAt ? (now - a.publishedAt.getTime()) / 3600_000 : WINDOW_HOURS;
    const score = a.impactScore
      + (topic ? topic.boost : -1)   // untopic'd stories only fill spare slots
      - ageHours / 24            // −1 point per day old
      - (company ? 1.5 : 0);     // prefer the market-wide headline of a story
    return [{ a, topic: topic?.id ?? 'other', score }];
  });

  scored.sort((x, y) => y.score - x.score);

  const picked: typeof scored = [];
  const perTopic: Record<string, number> = {};
  for (const s of scored) {
    if (picked.length >= MAX_ARTICLES) break;
    const limit = 1;
    if ((perTopic[s.topic] ?? 0) >= limit) continue;
    const words = significantWords(s.a.title);
    const dup = picked.some(p => {
      const pw = significantWords(p.a.title);
      return Array.from(words).filter(w => pw.has(w)).length >= 4;
    });
    if (dup) continue;
    perTopic[s.topic] = (perTopic[s.topic] ?? 0) + 1;
    picked.push(s);
  }

  // Shape matches the previous response (tickerId is internal only).
  const articles = picked.map(({ a }) => ({
    id: a.id, title: a.title, aiSummary: a.aiSummary, url: a.url, source: a.source,
    publishedAt: a.publishedAt, sentiment: a.sentiment, impactScore: a.impactScore,
    category: a.category, ticker: a.ticker,
  }));

  return NextResponse.json(articles);
}
