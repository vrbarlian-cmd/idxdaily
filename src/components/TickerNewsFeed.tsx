'use client';

import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Newspaper } from 'lucide-react';
import NewsCard from './NewsCard';
import ArchiveSection from './ArchiveSection';

interface MentionItem {
  id:            string;
  title:         string;
  aiSummary:     string | null;
  url:           string | null;
  source:        string;
  publishedAt:   string;
  sentiment:     string;
  impactScore:   number;
  category:      string;
  isEarlySignal: boolean;
  isMacroImpact: boolean;
}

interface Props {
  symbol:          string;
  tickerName:      string;
  sector:          string | null;
  allRecentNews:   MentionItem[];
  allArchiveItems: MentionItem[];
}

const SENTIMENTS = ['ALL', 'BULLISH', 'BEARISH', 'NEUTRAL'] as const;

/**
 * Client-side sentiment filtering — the server fetches the full unfiltered
 * 30-day feed + archive once (cacheable via ISR), and this component filters
 * the already-fetched data in the browser on toggle click. Keeps the sentiment
 * query param shareable/bookmarkable (read via useSearchParams) without the
 * page.tsx server component reading `searchParams`, which would otherwise
 * force the whole route to render dynamically on every request.
 */
export default function TickerNewsFeed({
  symbol, tickerName, sector, allRecentNews, allArchiveItems,
}: Props) {
  const searchParams = useSearchParams();
  const sentimentFilter = searchParams.get('sentiment')?.toUpperCase();

  const recentNews = sentimentFilter
    ? allRecentNews.filter(m => m.sentiment === sentimentFilter)
    : allRecentNews;

  const archiveItems = sentimentFilter
    ? allArchiveItems.filter(m => m.sentiment === sentimentFilter)
    : allArchiveItems;

  return (
    <>
      <div>
        <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-[#9ca3af]">Berita Terbaru</p>
            <p className="text-[10px] text-[#9ca3af] mt-0.5">30 hari terakhir · {recentNews.length} artikel</p>
          </div>
          <div className="flex flex-wrap gap-1">
            {SENTIMENTS.map((s) => {
              const isActive = s === 'ALL' ? !sentimentFilter : sentimentFilter === s;
              const href = s === 'ALL'
                ? `/saham/${symbol}`
                : `/saham/${symbol}?sentiment=${s}`;
              return (
                <Link
                  key={s}
                  href={href}
                  scroll={false}
                  className={`px-3 py-1 text-xs rounded-full border transition-all font-medium ${
                    isActive
                      ? s === 'BULLISH' ? 'bg-emerald-50 border-emerald-300 text-emerald-700'
                      : s === 'BEARISH' ? 'bg-red-50 border-red-300 text-red-600'
                      : s === 'NEUTRAL' ? 'bg-amber-50 border-amber-300 text-amber-700'
                      : 'bg-blue-50 border-blue-300 text-[#1a56db]'
                      : 'bg-white border-[#e5e2db] text-[#6b7280] hover:border-[#d1cdc7] hover:bg-[#f8f7f4]'
                  }`}
                >
                  {s}
                </Link>
              );
            })}
          </div>
        </div>
        <hr className="border-[#e5e2db]" />
      </div>

      {recentNews.length === 0 ? (
        <div className="bg-white border border-[#e5e2db] rounded-xl p-8 text-center space-y-3">
          <div className="flex justify-center">
            <Newspaper className="w-8 h-8 text-[#d1cdc7]" />
          </div>
          <p className="text-[#374151] font-medium text-sm">
            {sentimentFilter
              ? `Tidak ada berita ${sentimentFilter.toLowerCase()} untuk ${symbol} dalam 30 hari terakhir`
              : `Belum ada berita terbaru untuk ${symbol} dalam 30 hari terakhir`
            }
          </p>
          <p className="text-[#9ca3af] text-xs leading-relaxed max-w-xs mx-auto">
            {sentimentFilter
              ? 'Coba hapus filter sentimen, atau kembali lagi nanti.'
              : sector
                ? `${tickerName} belum muncul di sumber berita kami. Cek arsip di bawah untuk berita lama, atau lihat konteks makro sektor ${sector} di beranda.`
                : `${tickerName} belum muncul di sumber berita yang kami pantau. Kami terus menambah cakupan sumber berita secara berkala.`
            }
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {recentNews.map((item) => (
            <NewsCard key={item.id} news={item} isMacroImpact={item.isMacroImpact} />
          ))}
        </div>
      )}

      {archiveItems.length > 0 && (
        <ArchiveSection
          items={archiveItems}
          symbol={symbol}
          autoExpand={recentNews.length === 0}
        />
      )}
    </>
  );
}
