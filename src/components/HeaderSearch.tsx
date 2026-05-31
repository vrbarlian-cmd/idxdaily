'use client';

import { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Search } from 'lucide-react';

interface Ticker {
  id: string;
  symbol: string;
  name: string;
}

export default function HeaderSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Ticker[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Debounced autocomplete
  useEffect(() => {
    if (!query || query.length < 1) { setResults([]); setOpen(false); return; }
    const t = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/tickers?q=${encodeURIComponent(query)}`);
        const data = await res.json();
        setResults(Array.isArray(data) ? data.slice(0, 6) : []);
        setOpen(true);
      } catch { setResults([]); }
      finally { setLoading(false); }
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
    <div ref={containerRef} className="relative w-full max-w-[220px]">
      <form onSubmit={handleSubmit} className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-stone-400 pointer-events-none" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value.toUpperCase())}
          onKeyDown={handleKey}
          onFocus={() => results.length > 0 && setOpen(true)}
          placeholder="Cari saham…"
          maxLength={6}
          autoComplete="off"
          className="w-full pl-8 pr-3 py-1.5 text-xs border border-[#e5e2db] rounded-full bg-[#f8f7f4]
                     text-[#0f172a] placeholder-[#9ca3af]
                     focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-400
                     focus:bg-white transition-all duration-150"
        />
        {loading && (
          <span className="absolute right-2 top-1/2 -translate-y-1/2">
            <span className="block w-3 h-3 border-2 border-brand-400 border-t-transparent rounded-full animate-spin" />
          </span>
        )}
      </form>

      {open && results.length > 0 && (
        <div className="absolute top-full mt-1 left-0 right-0 z-[200] bg-white border border-stone-200
                        rounded-xl shadow-lg overflow-hidden">
          {results.map((t) => (
            <button
              key={t.id}
              onMouseDown={(e) => { e.preventDefault(); navigate(t.symbol); }}
              className="w-full text-left px-3 py-2 hover:bg-stone-50 flex items-center gap-2
                         border-b border-stone-100 last:border-b-0 transition-colors"
            >
              <span className="font-mono text-xs font-bold text-brand-700 w-12 flex-shrink-0">{t.symbol}</span>
              <span className="text-xs text-stone-500 truncate">{t.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
