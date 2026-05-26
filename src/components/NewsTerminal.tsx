'use client';

import { useState, useEffect } from 'react';
import NewsCard from './NewsCard';
import TickerOverview from './TickerOverview';

interface News {
  id: string;
  title: string;
  aiSummary: string | null;
  url: string | null;
  source: string;
  publishedAt: string;
  sentiment: string;
  impactScore: number;
  category: string;
  isEarlySignal: boolean;
  signalType?: string | null;
  signalConfidence?: number | null;
}

interface EarlySignal {
  id: string;
  signalType: string;
  title: string;
  description: string;
  reasoning: string;
  confidence: number;
  sentiment: string;
  sourceUrl?: string | null;
  detectedAt: string;
}

interface NewsTerminalProps {
  tickerSymbol: string;
}

export default function NewsTerminal({ tickerSymbol }: NewsTerminalProps) {
  const [news, setNews] = useState<News[]>([]);
  const [earlySignals, setEarlySignals] = useState<EarlySignal[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [filter, setFilter] = useState<'all' | 'bullish' | 'bearish' | 'neutral'>('all');
  const [ticker, setTicker] = useState<any>(null);

  useEffect(() => {
    loadNews(false);
  }, [tickerSymbol]);

  const loadNews = async (refresh: boolean = false) => {
    if (refresh) setIsRefreshing(true);
    else setIsLoading(true);

    try {
      const response = await fetch(
        `/api/news/${tickerSymbol}${refresh ? '?refresh=true' : ''}`
      );
      const data = await response.json();
      
      setTicker(data.ticker);
      setNews(data.news || []);
      setEarlySignals(data.earlySignals || []);
    } catch (error) {
      console.error('Error loading news:', error);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  const filteredNews = news.filter((item) => {
    if (filter === 'all') return true;
    return item.sentiment.toLowerCase() === filter;
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="animate-spin h-12 w-12 border-4 border-terminal-accent border-t-transparent rounded-full mx-auto mb-4"></div>
          <div className="text-gray-400">Loading news for {tickerSymbol}...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 fade-in">
      {/* Ticker Overview */}
      {ticker && <TickerOverview ticker={ticker} tickerSymbol={tickerSymbol} />}

      {/* Early Signals Section */}
      {earlySignals.length > 0 && (
        <div className="bg-terminal-secondary border border-terminal-accent rounded p-4">
          <h2 className="text-terminal-accent font-bold mb-3 flex items-center">
            <span className="mr-2">⚡</span>
            EARLY SIGNALS DETECTED ({earlySignals.length})
          </h2>
          <div className="space-y-3">
            {earlySignals.slice(0, 3).map((signal) => (
              <div
                key={signal.id}
                className="bg-terminal-bg border border-terminal-border rounded p-3"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1">
                    <div className="text-sm font-bold text-white mb-1">{signal.title}</div>
                    <div className="text-xs text-gray-400">{signal.description}</div>
                  </div>
                  <div className="ml-3 text-right">
                    <div className={`text-xs font-bold ${
                      signal.sentiment === 'BULLISH' ? 'text-terminal-green' :
                      signal.sentiment === 'BEARISH' ? 'text-terminal-red' :
                      'text-terminal-yellow'
                    }`}>
                      {signal.sentiment}
                    </div>
                    <div className="text-xs text-gray-500">
                      {Math.round(signal.confidence * 100)}% conf.
                    </div>
                  </div>
                </div>
                <div className="text-xs text-gray-500 mt-2">
                  <span className="text-terminal-accent">{signal.signalType}</span> • {signal.reasoning}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span className="text-sm text-gray-500">FILTER:</span>
          {(['all', 'bullish', 'bearish', 'neutral'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 text-xs rounded uppercase transition-colors ${
                filter === f
                  ? 'bg-terminal-accent text-white'
                  : 'bg-terminal-secondary text-terminal-text hover:bg-terminal-border'
              }`}
            >
              {f}
            </button>
          ))}
        </div>

        <button
          onClick={() => loadNews(true)}
          disabled={isRefreshing}
          className="px-4 py-2 text-sm bg-terminal-secondary text-terminal-text border border-terminal-border rounded hover:border-terminal-accent transition-colors disabled:opacity-50"
        >
          {isRefreshing ? (
            <span className="flex items-center">
              <div className="animate-spin h-4 w-4 border-2 border-terminal-accent border-t-transparent rounded-full mr-2"></div>
              FETCHING...
            </span>
          ) : (
            <span>↻ REFRESH NEWS</span>
          )}
        </button>
      </div>

      {/* News List */}
      {filteredNews.length === 0 ? (
        <div className="text-center py-12 bg-terminal-secondary border border-terminal-border rounded">
          <div className="text-gray-500 mb-4">No news found</div>
          <button
            onClick={() => loadNews(true)}
            className="px-6 py-3 bg-terminal-accent text-white rounded hover:bg-orange-600 transition-colors"
          >
            Fetch Latest News
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredNews.map((item) => (
            <NewsCard key={item.id} news={item} />
          ))}
        </div>
      )}
    </div>
  );
}
