'use client';

import { isToday } from 'date-fns';
import useSWR from 'swr';
import { useState } from 'react';
import { dedupArticles } from '@/lib/dedupArticles';
import { CompactNewsList, type CompactArticle } from '@/components/CompactNewsCard';

// ── Helpers ───────────────────────────────────────────────────────────────────

function isMarketHours(): boolean {
  const wibHour = new Date(
    new Date().toLocaleString('en-US', { timeZone: 'Asia/Jakarta' })
  ).getHours();
  return wibHour >= 9 && wibHour < 16;
}

// ── SWR fetcher ───────────────────────────────────────────────────────────────

const fetcher = (url: string) => fetch(url).then(r => r.json());

// ── Main component ────────────────────────────────────────────────────────────

export default function MacroMarketNews() {
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const { data: raw = [], isLoading } = useSWR<CompactArticle[]>(
    '/api/macro-news',
    fetcher,
    {
      refreshInterval:   60_000,
      revalidateOnFocus: true,
      onSuccess: () => setLastUpdated(new Date()),
    },
  );

  // Display-level dedup: shared topic-keyword + 4-word-overlap util
  const articles = dedupArticles(raw);

  const hasFresh = articles.some(a => a.publishedAt && isToday(new Date(a.publishedAt)));

  const updatedLabel = lastUpdated
    ? `Diperbarui ${lastUpdated.toLocaleTimeString('id-ID', {
        hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Jakarta',
      })} WIB`
    : null;

  return (
    <section>

      {/* Section header */}
      <div className="flex items-end justify-between gap-3 mb-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-[#9ca3af] mb-0.5">
            Makro &amp; Pasar
          </p>
          <h2 className="text-base md:text-sm font-bold text-[#0f172a]">
            Berita Makro &amp; Pasar
          </h2>
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          {isMarketHours() && (
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse flex-shrink-0" title="Live" />
          )}
          {updatedLabel && (
            <span className="text-[10px] text-[#9ca3af] tabular-nums">{updatedLabel}</span>
          )}
          {!isLoading && !hasFresh && articles.length > 0 && (
            <span className="hidden md:inline text-[11px] text-amber-700 bg-amber-50 border border-amber-100 rounded-full px-2.5 py-1 font-medium">
              Tidak ada berita makro baru hari ini
            </span>
          )}
          <span className="hidden md:inline text-[11px] text-[#9ca3af]">IHSG · BI Rate · Global</span>
        </div>
      </div>

      <hr className="border-[#e5e2db] mb-3" />

      {/* Articles */}
      {isLoading ? (
        <div className="space-y-2.5">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="bg-white border border-[#e5e2db] rounded-xl h-24 animate-pulse" />
          ))}
        </div>
      ) : articles.length > 0 ? (
        <CompactNewsList articles={articles} initial={4} showCategory />
      ) : (
        <div className="py-8 text-center text-sm text-[#9ca3af]">
          Hari ini tidak ada berita makro atau kebijakan berdampak tinggi.
          Bagian ini hanya menampilkan berita level-pasar, bukan berita emiten.
        </div>
      )}
    </section>
  );
}
