'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Search, Zap } from 'lucide-react';

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
    <section className="relative overflow-hidden border-b border-stone-200"
      style={{ background: 'linear-gradient(145deg, #f8faff 0%, #ffffff 45%, #f0fdf8 100%)' }}
    >
      {/* Subtle decorative blobs */}
      <div className="absolute top-0 right-0 w-64 h-64 rounded-full opacity-[0.04] blur-3xl pointer-events-none"
           style={{ background: 'radial-gradient(circle, #0ea5e9, transparent)', transform: 'translate(30%, -30%)' }} />
      <div className="absolute bottom-0 left-0 w-48 h-48 rounded-full opacity-[0.04] blur-3xl pointer-events-none"
           style={{ background: 'radial-gradient(circle, #10b981, transparent)', transform: 'translate(-30%, 30%)' }} />

      <div className="relative max-w-5xl mx-auto px-4 py-10 text-center">

        {/* Badge */}
        <div className="inline-flex items-center gap-1.5 bg-brand-50 border border-brand-200 text-brand-700 rounded-full px-3 py-1 text-xs font-semibold mb-4">
          <span className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse" />
          IDX Market Intelligence
        </div>

        {/* Title */}
        <h1 className="text-2xl sm:text-3xl font-bold text-stone-900 tracking-tight mb-2">
          Berita Saham Indonesia Bertenaga{' '}
          <span style={{
            background: 'linear-gradient(135deg, #7c3aed, #2563eb)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}>
            AI
          </span>
        </h1>
        <p className="text-sm text-stone-500 mb-8 max-w-md mx-auto leading-relaxed">
          Sentimen real-time, analisis dampak, dan ringkasan AI untuk pasar modal Indonesia.
        </p>

        {/* Search bar */}
        <form onSubmit={handleSubmit} className="flex gap-2 max-w-sm mx-auto mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400 pointer-events-none" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value.toUpperCase())}
              placeholder="Kode saham (mis. BBRI)"
              maxLength={6}
              className="w-full pl-9 pr-3 py-2.5 border border-stone-300 rounded-xl text-sm text-stone-900 placeholder-stone-400
                         bg-white shadow-sm
                         focus:outline-none focus:ring-2 focus:ring-brand-300 focus:border-brand-400
                         transition-all duration-200"
              style={{
                ['--tw-ring-shadow' as string]: '0 0 0 4px rgba(14,165,233,0.10)',
              }}
            />
          </div>
          <button
            type="submit"
            className="bg-brand-600 hover:bg-brand-700 active:bg-brand-800 text-white rounded-xl px-5 py-2.5 text-sm font-bold transition-all shadow-sm hover:shadow-md flex-shrink-0 flex items-center gap-1.5"
          >
            <Search className="w-3.5 h-3.5" />
            Cari
          </button>
        </form>

        {/* Popular tickers */}
        <div className="flex flex-wrap items-center justify-center gap-1.5">
          <span className="text-xs text-stone-400 mr-0.5 flex items-center gap-1">
            <Zap className="w-3 h-3 text-amber-400" />
            Populer:
          </span>
          {POPULAR.map((sym) => (
            <Link
              key={sym}
              href={`/saham/${sym}`}
              className="font-mono text-xs font-bold bg-white hover:bg-brand-50 border border-stone-200 hover:border-brand-300 text-stone-700 hover:text-brand-700 rounded-full px-3 py-1 transition-all duration-150 shadow-sm hover:shadow hover:scale-105"
            >
              {sym}
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
