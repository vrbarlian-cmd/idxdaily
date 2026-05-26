'use client';

import { useState } from 'react';

interface TerminalHeaderProps {
  onShowSignals: () => void;
  showingSignals: boolean;
}

export default function TerminalHeader({ onShowSignals, showingSignals }: TerminalHeaderProps) {
  const [time, setTime] = useState(new Date());

  useState(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  });

  return (
    <div className="bg-terminal-secondary border-b border-terminal-border">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          {/* Logo and Title */}
          <div className="flex items-center space-x-4">
            <div className="text-terminal-accent font-bold text-2xl">
              IDX<span className="text-terminal-text">:</span>TERMINAL
            </div>
            <div className="text-xs text-gray-500 hidden sm:block">
              Indonesian Equity Market Intelligence
            </div>
          </div>

          {/* Navigation and Clock */}
          <div className="flex items-center space-x-6">
            <button
              onClick={onShowSignals}
              className={`px-4 py-2 text-sm rounded transition-colors ${
                showingSignals
                  ? 'bg-terminal-accent text-white'
                  : 'bg-terminal-bg text-terminal-text hover:bg-terminal-border'
              }`}
            >
              <span className="mr-2">⚡</span>
              EARLY SIGNALS
            </button>
            
            <div className="text-right hidden md:block">
              <div className="text-xs text-gray-500">JAKARTA TIME</div>
              <div className="text-sm font-mono">
                {time.toLocaleTimeString('en-US', { 
                  timeZone: 'Asia/Jakarta',
                  hour12: false 
                })}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
