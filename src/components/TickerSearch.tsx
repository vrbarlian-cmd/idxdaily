'use client';

import { useState, useEffect, useCallback } from 'react';

interface Ticker {
  id: string;
  symbol: string;
  name: string;
  sector?: string;
  subsector?: string;
}

interface TickerSearchProps {
  onTickerSelect: (symbol: string) => void;
  selectedTicker: string | null;
}

export default function TickerSearch({ onTickerSelect, selectedTicker }: TickerSearchProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Ticker[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showResults, setShowResults] = useState(false);

  const searchTickers = useCallback(async (searchQuery: string) => {
    if (!searchQuery) {
      setResults([]);
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(`/api/tickers?q=${encodeURIComponent(searchQuery)}`);
      const data = await response.json();
      setResults(data);
      setShowResults(true);
    } catch (error) {
      console.error('Error searching tickers:', error);
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const debounce = setTimeout(() => {
      searchTickers(query);
    }, 300);

    return () => clearTimeout(debounce);
  }, [query, searchTickers]);

  const handleSelect = (ticker: Ticker) => {
    setQuery(ticker.symbol);
    setShowResults(false);
    onTickerSelect(ticker.symbol);
  };

  return (
    <div className="relative">
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value.toUpperCase())}
          onFocus={() => query && setShowResults(true)}
          placeholder="ENTER TICKER SYMBOL (e.g., BBCA, BBRI, MDKA)..."
          className="w-full bg-terminal-secondary text-terminal-text border border-terminal-border rounded px-6 py-4 text-lg font-mono focus:outline-none focus:border-terminal-accent transition-colors"
          autoComplete="off"
        />
        {isLoading && (
          <div className="absolute right-4 top-1/2 -translate-y-1/2">
            <div className="animate-spin h-5 w-5 border-2 border-terminal-accent border-t-transparent rounded-full"></div>
          </div>
        )}
      </div>

      {/* Search Results */}
      {showResults && results.length > 0 && (
        <div className="absolute z-10 w-full mt-2 bg-terminal-secondary border border-terminal-border rounded shadow-xl max-h-96 overflow-y-auto">
          {results.map((ticker) => (
            <button
              key={ticker.id}
              onClick={() => handleSelect(ticker)}
              className="w-full text-left px-4 py-3 hover:bg-terminal-bg transition-colors border-b border-terminal-border last:border-b-0"
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-terminal-accent font-bold">{ticker.symbol}</div>
                  <div className="text-sm text-terminal-text">{ticker.name}</div>
                </div>
                <div className="text-xs text-gray-500">
                  {ticker.sector && (
                    <div>{ticker.sector}</div>
                  )}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Popular Tickers */}
      {!query && !selectedTicker && (
        <div className="mt-4 text-sm">
          <div className="text-gray-500 mb-2">Popular Tickers:</div>
          <div className="flex flex-wrap gap-2">
            {['BBCA', 'BBRI', 'BMRI', 'TLKM', 'ASII', 'GOTO', 'MDKA', 'AMMN'].map((symbol) => (
              <button
                key={symbol}
                onClick={() => {
                  setQuery(symbol);
                  onTickerSelect(symbol);
                }}
                className="px-3 py-1 bg-terminal-secondary border border-terminal-border rounded hover:border-terminal-accent transition-colors"
              >
                {symbol}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
