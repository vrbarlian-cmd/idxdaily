'use client';

import { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Search } from 'lucide-react';

interface Ticker {
  id:     string;
  symbol: string;
  name:   string;
}

interface Props {
  popularTickers: string[];
}

export default function HeroSearch({ popularTickers }: Props) {
  const [query,   setQuery]   = useState('');
  const [results, setResults] = useState<Ticker[]>([]);
  const [open,    setOpen]    = useState(false);
  const [loading, setLoading] = useState(false);
  const router       = useRouter();
  const inputRef     = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Debounced autocomplete — same endpoint as HeaderSearch
  useEffect(() => {
    if (!query || query.length < 1) { setResults([]); setOpen(false); return; }
    const t = setTimeout(async () => {
      setLoading(true);
      try {
        const res  = await fetch(`/api/tickers?q=${encodeURIComponent(query)}`);
        const data = await res.json();
        setResults(Array.isArray(data) ? data.slice(0, 7) : []);
        setOpen(true);
      } catch { setResults([]); }
      finally  { setLoading(false); }
    }, 200);
    return () => clearTimeout(t);
  }, [query]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const navigate = (sym: string) => {
    const upper = sym.trim().toUpperCase();
    if (!upper) return;
    setQuery('');
    setOpen(false);
    // Fire-and-forget search log — non-blocking, errors ignored
    fetch('/api/search-log', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ symbol: upper }),
    }).catch(() => {});
    router.push(`/saham/${upper}`);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) navigate(query);
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') { setOpen(false); inputRef.current?.blur(); }
  };

  return (
    <section className="border-b border-[#e5e2db] bg-[#f8f7f4]">
      <div className="max-w-5xl mx-auto px-4 py-5 text-center">

        {/* Search bar with autocomplete */}
        <div ref={containerRef} className="relative max-w-sm mx-auto mb-4">
          <form onSubmit={handleSubmit} className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#9ca3af] pointer-events-none" />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value.toUpperCase())}
                onKeyDown={handleKey}
                onFocus={() => results.length > 0 && setOpen(true)}
                placeholder="Kode saham (mis. BBRI)"
                maxLength={6}
                autoComplete="off"
                className="w-full pl-10 pr-3 py-2.5 border border-[#e5e2db] rounded-full text-sm
                           text-[#0f172a] placeholder-[#9ca3af] bg-white shadow-sm
                           focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-400
                           transition-all duration-200"
              />
              {loading && (
                <span className="absolute right-3 top-1/2 -translate-y-1/2">
                  <span className="block w-3.5 h-3.5 border-2 border-[#1a56db] border-t-transparent rounded-full animate-spin" />
                </span>
              )}
            </div>
            <button
              type="submit"
              className="bg-[#1a56db] hover:bg-blue-700 active:bg-blue-800 text-white rounded-full px-5 py-2.5 text-sm font-semibold transition-all shadow-sm flex-shrink-0 flex items-center gap-1.5"
            >
              <Search className="w-3.5 h-3.5" />
              Cari
            </button>
          </form>

          {/* Autocomplete dropdown */}
          {open && results.length > 0 && (
            <div className="absolute top-full mt-1.5 left-0 right-12 z-[200] bg-white border border-[#e5e2db] rounded-xl shadow-lg overflow-hidden">
              {results.map((t) => (
                <button
                  key={t.id}
                  onMouseDown={(e) => { e.preventDefault(); navigate(t.symbol); }}
                  className="w-full text-left px-3 py-2.5 hover:bg-[#f8f7f4] flex items-center gap-2.5
                             border-b border-[#f0ede8] last:border-b-0 transition-colors"
                >
                  <span className="font-mono text-xs font-bold text-[#1a56db] w-14 flex-shrink-0">{t.symbol}</span>
                  <span className="text-xs text-[#6b7280] truncate">{t.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Popular tickers */}
        <div className="flex flex-wrap items-center justify-center gap-1.5">
          <span className="text-xs text-[#9ca3af] mr-0.5">Populer:</span>
          {popularTickers.map((sym) => (
            <Link
              key={sym}
              href={`/saham/${sym}`}
              onClick={() => {
                fetch('/api/search-log', {
                  method:  'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body:    JSON.stringify({ symbol: sym }),
                }).catch(() => {});
              }}
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
