'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Search } from 'lucide-react';

const POPULAR = ['BBCA', 'BBRI', 'BMRI', 'BBNI', 'GOTO', 'TLKM', 'ASII', 'BUMI', 'PTRO'];

export default function HeroSearch() {
  const [query, setQuery] = useState('');
  const router = useRouter();

  const navigate = (sym: string) => {
    const upper = sym.trim().toUpperCase();
    if (!upper) return;
    setQuery('');
    router.push(`/saham/${upper}`);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) navigate(query);
  };

  return (
    <section className="border-b border-[#e5e2db] bg-[#f8f7f4]">
      <div className="max-w-5xl mx-auto px-4 py-8 text-center">

        {/* Title */}
        <h1 className="text-2xl sm:text-3xl font-bold text-[#0f172a] tracking-tight mb-1.5">
          Berita Saham Indonesia Bertenaga{' '}
          <span style={{
            background: 'linear-gradient(135deg, #7c3aed, #2563eb)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}>
            AI
          </span>
        </h1>
        <p className="text-sm text-[#6b7280] mb-6 max-w-md mx-auto leading-relaxed">
          Sentimen real-time, analisis dampak, dan ringkasan AI untuk pasar modal Indonesia.
        </p>

        {/* Search bar */}
        <form onSubmit={handleSubmit} className="flex gap-2 max-w-sm mx-auto mb-5">
          <div className="relative flex-1">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#9ca3af] pointer-events-none" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value.toUpperCase())}
              placeholder="Kode saham (mis. BBRI)"
              maxLength={6}
              className="w-full pl-10 pr-3 py-2.5 border border-[#e5e2db] rounded-full text-sm text-[#0f172a] placeholder-[#9ca3af]
                         bg-white shadow-sm
                         focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-400
                         transition-all duration-200"
            />
          </div>
          <button
            type="submit"
            className="bg-[#1a56db] hover:bg-blue-700 active:bg-blue-800 text-white rounded-full px-5 py-2.5 text-sm font-semibold transition-all shadow-sm flex-shrink-0 flex items-center gap-1.5"
          >
            <Search className="w-3.5 h-3.5" />
            Cari
          </button>
        </form>

        {/* Popular tickers */}
        <div className="flex flex-wrap items-center justify-center gap-1.5">
          <span className="text-xs text-[#9ca3af] mr-0.5">Populer:</span>
          {POPULAR.map((sym) => (
            <Link
              key={sym}
              href={`/saham/${sym}`}
              className="font-mono text-xs font-bold bg-white hover:bg-blue-50 border border-[#e5e2db] hover:border-blue-300 text-[#374151] hover:text-[#1a56db] rounded-full px-3 py-1 transition-all duration-150"
            >
              {sym}
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
