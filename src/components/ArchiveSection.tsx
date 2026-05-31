'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, Archive } from 'lucide-react';
import NewsCard from './NewsCard';

interface ArchiveItem {
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
  items:      ArchiveItem[];
  symbol:     string;
  /** True when the recent-news section is empty — auto-expand archive in that case */
  autoExpand?: boolean;
}

/**
 * Collapsible "Arsip" section — shows older real news with unmistakably clear age labels.
 * The age is already shown per-article by NewsCard (via formatDistanceToNow).
 * This section itself carries a header warning that the news is older than 30 days.
 *
 * Rules:
 *  - Only shown when caller decides it's appropriate (sparse or empty recent news).
 *  - Every article is real, really about this ticker, enriched.
 *  - The section header makes the age context unmistakable.
 *  - DO NOT mix with the live feed; this is always a separate, labeled section.
 */
export default function ArchiveSection({ items, symbol, autoExpand = false }: Props) {
  const [open, setOpen] = useState(autoExpand);

  if (items.length === 0) return null;

  return (
    <div className="mt-6">
      {/* Section header / toggle */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-[#f8f7f4] border border-[#e5e2db] rounded-xl text-sm font-semibold text-[#6b7280] hover:bg-[#f0ede8] transition-colors"
        aria-expanded={open}
      >
        <span className="flex items-center gap-2">
          <Archive className="w-4 h-4 text-[#9ca3af]" />
          Arsip — {items.length} berita lama ({'>'}30 hari)
        </span>
        <span className="flex items-center gap-1.5 text-xs font-normal text-[#9ca3af]">
          <span className="hidden sm:inline">Setiap artikel sudah jelas tanggalnya</span>
          {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </span>
      </button>

      {open && (
        <div className="mt-3 space-y-3">
          {/* Disclaimer banner */}
          <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-xs text-amber-800">
            <span className="text-base leading-none mt-0.5">⚠</span>
            <span>
              Berita di bawah ini <strong>lebih dari 30 hari</strong> dan mungkin sudah tidak relevan.
              Usianya ditampilkan di setiap kartu. Jangan gunakan sebagai sinyal trading terkini.
            </span>
          </div>
          {items.map(item => (
            <NewsCard key={item.id} news={item} isMacroImpact={item.isMacroImpact} />
          ))}
        </div>
      )}
    </div>
  );
}
