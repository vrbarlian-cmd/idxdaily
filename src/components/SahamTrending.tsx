import Link from 'next/link';
import { unstable_cache } from 'next/cache';
import { getTrending24h } from '@/lib/trending';
import { getIndexableSymbols } from '@/lib/tickerSeo';

// Homepage "Saham Trending": top 10 tickers by 24h article count, limited to
// tickers whose pages are indexable (>= INDEX_MIN_ARTICLES_30D), each linking
// to /saham/[ticker]. Cached 10 min; renders nothing on error or empty data.

const cachedTrending = unstable_cache(() => getTrending24h(30), ['saham-trending-24h-v1'], { revalidate: 600 });

function dot(s: string) {
  if (s === 'BULLISH') return 'bg-emerald-500';
  if (s === 'BEARISH') return 'bg-red-500';
  return 'bg-amber-400';
}

export default async function SahamTrending() {
  let items: Awaited<ReturnType<typeof getTrending24h>> = [];
  try {
    const [trending, indexable] = await Promise.all([cachedTrending(), getIndexableSymbols()]);
    items = (trending ?? []).filter(t => indexable.has(t.ticker)).slice(0, 10);
  } catch (err) {
    console.error('[SahamTrending] failed:', err);
    return null;
  }
  if (!items.length) return null;

  return (
    <section aria-labelledby="saham-trending">
      <div className="flex items-end justify-between gap-3 mb-2">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-[#9ca3af] mb-0.5">24 Jam Terakhir</p>
          <h2 id="saham-trending" className="text-base md:text-sm font-bold text-[#0f172a]">Saham Trending</h2>
        </div>
      </div>
      <ol className="flex flex-wrap gap-1.5">
        {items.map((t, i) => (
          <li key={t.ticker}>
            <Link
              href={`/saham/${t.ticker}`}
              title={`${t.name} · ${t.article_count_24h} berita dalam 24 jam`}
              className="inline-flex items-center gap-1.5 bg-white border border-[#e5e2db] hover:border-blue-300 rounded-full pl-2 pr-2.5 py-1 transition-colors"
            >
              <span className="text-[10px] text-[#9ca3af] tabular-nums">{i + 1}</span>
              <span className={`w-1.5 h-1.5 rounded-full ${dot(t.dominant_sentiment)}`} />
              <span className="font-mono text-xs font-bold text-[#0f172a]">{t.ticker}</span>
              <span className="text-[10px] text-[#9ca3af] tabular-nums">{t.article_count_24h}</span>
            </Link>
          </li>
        ))}
      </ol>
    </section>
  );
}
