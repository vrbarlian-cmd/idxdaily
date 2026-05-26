'use client';

import { useState, useEffect } from 'react';
import { formatDistanceToNow } from 'date-fns';

interface EarlySignal {
  id: string;
  tickerSymbol: string;
  signalType: string;
  title: string;
  description: string;
  reasoning: string;
  confidence: number;
  sentiment: string;
  sourceUrl?: string | null;
  detectedAt: string;
}

export default function EarlySignals() {
  const [signals, setSignals] = useState<EarlySignal[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadSignals();
  }, []);

  const loadSignals = async () => {
    setIsLoading(true);
    try {
      const response = await fetch('/api/signals?limit=20');
      const data = await response.json();
      setSignals(data);
    } catch (error) {
      console.error('Error loading signals:', error);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="animate-spin h-12 w-12 border-4 border-terminal-accent border-t-transparent rounded-full mx-auto mb-4"></div>
          <div className="text-gray-400">Loading early signals...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 fade-in">
      <div className="bg-terminal-secondary border border-terminal-border rounded-lg p-6">
        <h1 className="text-2xl font-bold text-terminal-accent mb-2 flex items-center">
          <span className="mr-2">⚡</span>
          EARLY SIGNALS
        </h1>
        <p className="text-gray-400 text-sm">
          AI-detected market signals that may not be fully priced in yet
        </p>
      </div>

      {signals.length === 0 ? (
        <div className="text-center py-12 bg-terminal-secondary border border-terminal-border rounded">
          <div className="text-gray-500">No early signals detected yet</div>
        </div>
      ) : (
        <div className="grid gap-4">
          {signals.map((signal) => (
            <div
              key={signal.id}
              className="bg-terminal-secondary border border-terminal-border rounded-lg p-5 hover:border-terminal-accent transition-colors"
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1">
                  <div className="flex items-center space-x-2 mb-2">
                    <span className="px-2 py-1 text-xs font-bold bg-terminal-accent text-white rounded">
                      {signal.tickerSymbol}
                    </span>
                    <span className="px-2 py-1 text-xs bg-terminal-bg border border-terminal-border rounded">
                      {signal.signalType}
                    </span>
                    <span
                      className={`text-xs font-bold ${
                        signal.sentiment === 'BULLISH'
                          ? 'text-terminal-green'
                          : signal.sentiment === 'BEARISH'
                          ? 'text-terminal-red'
                          : 'text-terminal-yellow'
                      }`}
                    >
                      {signal.sentiment}
                    </span>
                  </div>
                  
                  <h3 className="text-white font-bold text-lg mb-2 leading-tight">
                    {signal.title}
                  </h3>
                  
                  <p className="text-gray-300 text-sm mb-3 leading-relaxed">
                    {signal.description}
                  </p>
                </div>

                <div className="ml-4 text-right">
                  <div className="text-2xl font-bold text-terminal-accent">
                    {Math.round(signal.confidence * 100)}%
                  </div>
                  <div className="text-xs text-gray-500">CONFIDENCE</div>
                </div>
              </div>

              {/* Reasoning */}
              <div className="bg-terminal-bg border border-terminal-border rounded p-3 mb-3">
                <div className="text-xs text-gray-500 mb-1">AI REASONING</div>
                <div className="text-sm text-gray-300">{signal.reasoning}</div>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between text-xs text-gray-500">
                <span>
                  Detected {formatDistanceToNow(new Date(signal.detectedAt), { addSuffix: true })}
                </span>
                
                {signal.sourceUrl && (
                  <a
                    href={signal.sourceUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-terminal-accent hover:underline"
                  >
                    VIEW SOURCE →
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
