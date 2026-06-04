import { Sparkles } from 'lucide-react';
import { prisma } from '@/lib/prisma';
import Link from 'next/link';
import { format, isToday, formatDistanceToNow } from 'date-fns';
import { id as localeId } from 'date-fns/locale';

// ── Helpers ───────────────────────────────────────────────────────────────────

function accentBar(s: string) {
  if (s === 'BULLISH') return 'border-l-emerald-500';
  if (s === 'BEARISH') return 'border-l-red-500';
  return 'border-l-amber-400';
}
function bgTint(s: string) {
  if (s === 'BULLISH') return 'bg-emerald-50/10';
  if (s === 'BEARISH') return 'bg-red-50/15';
  return '';
}
function sentimentDot(s: string) {
  if (s === 'BULLISH') return 'bg-emerald-500';
  if (s === 'BEARISH') return 'bg-red-500';
  return 'bg-amber-400';
}
function sentimentLabel(s: string) {
  if (s === 'BULLISH') return 'Bullish';
  if (s === 'BEARISH') return 'Bearish';
  return 'Netral';
}
function sentimentTextColor(s: string) {
  if (s === 'BULLISH') return 'text-emerald-700';
  if (s === 'BEARISH') return 'text-red-600';
  return 'text-amber-700';
}
function impactColor(s: string) {
  if (s === 'BULLISH') return 'text-[#1D9E75]';
  if (s === 'BEARISH') return 'text-[#E24B4A]';
  if (s === 'NEUTRAL')  return 'text-[#F59E0B]';
  return 'text-[#94A3B8]';
}
function categoryBadge(c: string | null) {
  if (c === 'MACRO')      return 'bg-blue-50 text-blue-700 border-blue-100';
  if (c === 'REGULATORY') return 'bg-violet-50 text-violet-700 border-violet-100';
  if (c === 'SECTOR')     return 'bg-sky-50 text-sky-700 border-sky-100';
  return 'bg-[#f8f7f4] text-[#9ca3af] border-[#e5e2db]';
}

// ── Date badge ────────────────────────────────────────────────────────────────

function PubDate({ date }: { date: Date | null }) {
  if (!date) return null;
  if (isToday(date)) {
    const wib = date.toLocaleTimeString('id-ID', {
      hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Jakarta',
    });
    return (
      <span className="text-[11px] text-[#9ca3af] tabular-nums">
        {wib} WIB
      </span>
    );
  }
  const label = format(date, 'd MMM', { locale: localeId });
  const ago   = formatDistanceToNow(date, { addSuffix: true, locale: localeId });
  return (
    <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-100">
      {label} · {ago}
    </span>
  );
}

// ── Article card ──────────────────────────────────────────────────────────────

interface Article {
  id:          string;
  title:       string;
  aiSummary:   string | null;
  url:         string | null;
  source:      string;
  publishedAt: Date | null;
  sentiment:   string;
  impactScore: number;
  category:    string | null;
  ticker:      { symbol: string } | null;
}

function MacroCard({ a }: { a: Article }) {
  return (
    <div
      className={`
        relative bg-white border border-[#e5e2db] border-l-4 ${accentBar(a.sentiment)}
        ${bgTint(a.sentiment)} rounded-xl overflow-hidden
        transition-shadow duration-200 hover:shadow-sm
      `}
    >
      <div className="p-4 pl-5">

        {/* Badge row */}
        <div className="flex items-center gap-2 mb-2.5 flex-wrap">

          {/* Category */}
          {a.category && (
            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold border uppercase tracking-wide flex-shrink-0 ${categoryBadge(a.category)}`}>
              {a.category}
            </span>
          )}

          {/* Sentiment — dot + plain text, no pill */}
          <span className={`inline-flex items-center gap-1.5 text-xs font-semibold flex-shrink-0 ${sentimentTextColor(a.sentiment)}`}>
            <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${sentimentDot(a.sentiment)}`} />
            {sentimentLabel(a.sentiment)}
          </span>

          {/* AI badge — plain, no gradient */}
          {a.aiSummary && (
            <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-[#1a56db] flex-shrink-0">
              <Sparkles className="w-2.5 h-2.5" />
              AI
            </span>
          )}

          {/* Ticker chip */}
          {a.ticker && (
            <Link
              href={`/saham/${a.ticker.symbol}`}
              className="font-mono text-[10px] font-bold bg-[#0f172a] hover:bg-[#1e293b] text-white rounded px-1.5 py-0.5 transition-colors flex-shrink-0"
            >
              {a.ticker.symbol}
            </Link>
          )}

          {/* Source + date — right-aligned */}
          <div className="ml-auto flex items-center gap-2 flex-shrink-0">
            <span className="text-[11px] text-[#9ca3af]">{a.source}</span>
            <PubDate date={a.publishedAt} />
          </div>
        </div>

        {/* Title + impact score */}
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <p className="text-sm font-bold text-[#0f172a] leading-snug mb-1.5 line-clamp-2">
              {a.title}
            </p>
            {a.aiSummary && (
              <p className="text-xs text-[#4b5563] leading-relaxed line-clamp-2">
                {a.aiSummary}
              </p>
            )}
          </div>

          {/* Impact score */}
          <div className="flex-shrink-0 text-right pt-0.5">
            <span className={`text-xl font-bold leading-none tabular-nums ${impactColor(a.sentiment)}`}>
              {a.impactScore.toFixed(1)}
            </span>
            <p className="text-[10px] text-[#9ca3af]">/10</p>
            {a.url && (
              <a
                href={a.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block mt-1 text-[11px] text-[#1a56db] hover:text-blue-700 font-semibold"
              >
                Baca →
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Company-specific title filter ─────────────────────────────────────────────

const MACRO_ACRONYMS = new Set([
  'BI', 'OJK', 'BEI', 'LPS', 'KSSK', 'LPS',
  'IHSG', 'LQ45', 'IDX', 'IDR', 'USD', 'EUR', 'JPY', 'CNY', 'SGD',
  'US', 'EU', 'UK', 'IMF', 'WTO', 'OPEC', 'G20', 'G7',
  'Fed', 'ECB', 'BOJ', 'RBI',
  'MSCI', 'FTSE', 'DJIA', 'SPX', 'DXY',
  'GDP', 'PMI', 'CPI', 'PPI', 'SBN', 'ETF', 'IPO',
  'APBN', 'APBD', 'PPN', 'PPh', 'BUMN', 'PNBP',
]);

function looksCompanySpecific(title: string): boolean {
  if (/^saham[\s-]/i.test(title)) return true;
  if (/\bemiten\s+[A-Z]{2,5}\b/i.test(title)) return true;
  if (/\bdividen\b/i.test(title)) return true;
  if (/^(laba|rugi|pendapatan)\s+[A-Z]{2,5}\b/i.test(title)) return true;
  const leadWord = title.match(/^([A-Z]{2,5})(?=[\s:])/)?.[1];
  if (leadWord && !MACRO_ACRONYMS.has(leadWord)) return true;
  return false;
}

// ── Main component ────────────────────────────────────────────────────────────

export default async function MacroMarketNews() {
  const GLOBAL_SOURCES = [
    'Bloomberg Markets', 'CNBC International', 'Investing.com', 'Federal Reserve',
  ];

  const raw = await prisma.news.findMany({
    where: {
      aiSummary: { not: null },
      tickerId:  null,
      OR: [
        // Domestic sources — keep impact score threshold to filter noise
        { category: 'MACRO',      impactScore: { gte: 5.5 }, source: { notIn: GLOBAL_SOURCES } },
        { category: 'REGULATORY', impactScore: { gte: 5.5 }, source: { notIn: GLOBAL_SOURCES } },
        { category: 'SECTOR',     impactScore: { gte: 7.0 }, source: { notIn: GLOBAL_SOURCES } },
        // Global sources — 4.5 floor filters pure noise while keeping
        // conservative Gemini scores (4.0-5.5) for genuinely relevant items.
        { source: { in: GLOBAL_SOURCES }, aiSummary: { not: null }, impactScore: { gte: 4.5 } },
      ],
    },
    orderBy: [
      { publishedAt: 'desc' },
      { impactScore:  'desc' },
    ],
    take: 12,
    select: {
      id: true, title: true, aiSummary: true, url: true, source: true,
      publishedAt: true, sentiment: true, impactScore: true, category: true,
      ticker: { select: { symbol: true } },
    },
  });

  const articles = raw
    .filter(a => !looksCompanySpecific(a.title))
    .slice(0, 6);

  const hasFresh = articles.some(a => a.publishedAt && isToday(a.publishedAt));

  return (
    <section>

      {/* Section header */}
      <div className="flex items-center justify-between mb-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-[#9ca3af] mb-0.5">
            Makro &amp; Pasar
          </p>
          <h2 className="text-sm font-bold text-[#0f172a]">
            Berita Makro &amp; Pasar
          </h2>
        </div>
        <div className="flex items-center gap-2">
          {(!hasFresh || articles.length === 0) && (
            <span className="text-[11px] text-amber-700 bg-amber-50 border border-amber-100 rounded-full px-2.5 py-1 font-medium">
              Tidak ada berita makro baru hari ini
            </span>
          )}
          <span className="text-[11px] text-[#9ca3af]">IHSG · BI Rate · Global</span>
        </div>
      </div>

      <hr className="border-[#e5e2db] mb-4" />

      {/* Articles */}
      {articles.length > 0 ? (
        <div className="space-y-3">
          {articles.map(a => (
            <MacroCard key={a.id} a={a} />
          ))}
        </div>
      ) : (
        <div className="py-8 text-center text-sm text-[#9ca3af]">
          Hari ini tidak ada berita makro atau kebijakan berdampak tinggi.
          Bagian ini hanya menampilkan berita level-pasar, bukan berita emiten.
        </div>
      )}
    </section>
  );
}
