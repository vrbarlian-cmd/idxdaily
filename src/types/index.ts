/**
 * Type definitions for the IDX Terminal
 */

export interface Ticker {
  id: string;
  symbol: string;
  name: string;
  sector?: string | null;
  subsector?: string | null;
  description?: string | null;
  marketCap?: number | null;
  createdAt: Date;
  updatedAt: Date;
}

export interface News {
  id: string;
  tickerId: string;
  title: string;
  originalSummary?: string | null;
  aiSummary?: string | null;
  url?: string | null;
  source: string;
  publishedAt: Date;
  sentiment: Sentiment;
  impactScore: number;
  category: NewsCategory;
  isEarlySignal: boolean;
  signalType?: string | null;
  signalConfidence?: number | null;
  metadata?: string | null;
  createdAt: Date;
  updatedAt: Date;
}

export type Sentiment = 'BULLISH' | 'BEARISH' | 'NEUTRAL';

export type NewsCategory = 
  | 'CORPORATE'
  | 'FINANCIAL'
  | 'MACRO'
  | 'REGULATORY'
  | 'SECTOR'
  | 'DISCLOSURE'
  | 'GENERAL';

export interface EarlySignal {
  id: string;
  tickerSymbol: string;
  signalType: SignalType;
  title: string;
  description: string;
  reasoning: string;
  confidence: number;
  sentiment: Sentiment;
  sourceUrl?: string | null;
  metadata?: string | null;
  detectedAt: Date;
}

export type SignalType = 
  | 'FILING'
  | 'COMMODITY'
  | 'MACRO'
  | 'REGULATORY'
  | 'INSIDER';

export interface MacroIndicator {
  id: string;
  name: string;
  value: number;
  previousValue?: number | null;
  unit?: string | null;
  source: string;
  publishedAt: Date;
  impact?: string | null;
  createdAt: Date;
}

export interface TickerSummary {
  ticker: Ticker;
  summary: string;
  sentimentDistribution: {
    BULLISH: number;
    BEARISH: number;
    NEUTRAL: number;
  };
  averageImpactScore: number;
  newsCount: number;
}

export interface NewsResponse {
  ticker: Ticker;
  news: News[];
  earlySignals: EarlySignal[];
  count: number;
}
