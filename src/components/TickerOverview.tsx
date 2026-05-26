'use client';

import { useState, useEffect } from 'react';

interface TickerOverviewProps {
  ticker: {
    symbol: string;
    name: string;
    sector?: string;
    subsector?: string;
  };
  tickerSymbol: string;
}

export default function TickerOverview({ ticker, tickerSymbol }: TickerOverviewProps) {
  const [summary, setSummary] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadSummary();
  }, [tickerSymbol]);

  const loadSummary = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`/api/summary/${tickerSymbol}`);
      const data = await response.json();
      setSummary(data);
    } catch (error) {
      console.error('Error loading summary:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const totalSentiment = summary
    ? summary.sentimentDistribution.BULLISH +
      summary.sentimentDistribution.BEARISH +
      summary.sentimentDistribution.NEUTRAL
    : 0;

  const sentimentPercentages = summary
    ? {
        BULLISH: totalSentiment
          ? (summary.sentimentDistribution.BULLISH / totalSentiment) * 100
          : 0,
        BEARISH: totalSentiment
          ? (summary.sentimentDistribution.BEARISH / totalSentiment) * 100
          : 0,
        NEUTRAL: totalSentiment
          ? (summary.sentimentDistribution.NEUTRAL / totalSentiment) * 100
          : 0,
      }
    : null;

  return (
    <div className="bg-terminal-secondary border border-terminal-border rounded-lg p-6 mb-6">
      {/* Ticker Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="text-3xl font-bold text-terminal-accent mb-2">
            {ticker.symbol}
          </div>
          <div className="text-white text-lg mb-1">{ticker.name}</div>
          {ticker.sector && (
            <div className="text-sm text-gray-500">
              {ticker.sector}
              {ticker.subsector && ` • ${ticker.subsector}`}
            </div>
          )}
        </div>
      </div>

      {/* AI Summary */}
      {!isLoading && summary?.summary && (
        <div className="bg-terminal-bg border border-terminal-border rounded p-4 mb-6">
          <div className="text-terminal-accent text-sm font-bold mb-2">
            AI MARKET IMPACT SUMMARY
          </div>
          <p className="text-gray-300 text-sm leading-relaxed">{summary.summary}</p>
        </div>
      )}

      {/* Sentiment Distribution */}
      {!isLoading && sentimentPercentages && (
        <div>
          <div className="text-sm text-gray-500 mb-3">SENTIMENT DISTRIBUTION</div>
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-terminal-bg border border-terminal-border rounded p-3">
              <div className="text-terminal-green text-2xl font-bold mb-1">
                {sentimentPercentages.BULLISH.toFixed(0)}%
              </div>
              <div className="text-xs text-gray-500">
                BULLISH ({summary.sentimentDistribution.BULLISH})
              </div>
            </div>
            
            <div className="bg-terminal-bg border border-terminal-border rounded p-3">
              <div className="text-terminal-red text-2xl font-bold mb-1">
                {sentimentPercentages.BEARISH.toFixed(0)}%
              </div>
              <div className="text-xs text-gray-500">
                BEARISH ({summary.sentimentDistribution.BEARISH})
              </div>
            </div>
            
            <div className="bg-terminal-bg border border-terminal-border rounded p-3">
              <div className="text-terminal-yellow text-2xl font-bold mb-1">
                {sentimentPercentages.NEUTRAL.toFixed(0)}%
              </div>
              <div className="text-xs text-gray-500">
                NEUTRAL ({summary.sentimentDistribution.NEUTRAL})
              </div>
            </div>
          </div>
        </div>
      )}

      {isLoading && (
        <div className="text-center py-6">
          <div className="animate-spin h-8 w-8 border-2 border-terminal-accent border-t-transparent rounded-full mx-auto"></div>
        </div>
      )}
    </div>
  );
}
