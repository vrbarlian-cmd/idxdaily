/**
 * Utility functions for the IDX Terminal
 */

/**
 * Format large numbers with proper separators
 */
export function formatNumber(num: number): string {
  if (num >= 1e12) return `${(num / 1e12).toFixed(2)}T`;
  if (num >= 1e9) return `${(num / 1e9).toFixed(2)}B`;
  if (num >= 1e6) return `${(num / 1e6).toFixed(2)}M`;
  if (num >= 1e3) return `${(num / 1e3).toFixed(2)}K`;
  return num.toFixed(2);
}

/**
 * Format currency in Indonesian Rupiah
 */
export function formatIDR(amount: number): string {
  return new Intl.NumberFormat('id-ID', {
    style: 'currency',
    currency: 'IDR',
    minimumFractionDigits: 0,
  }).format(amount);
}

/**
 * Truncate text with ellipsis
 */
export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
}

/**
 * Get sentiment color class
 */
export function getSentimentColor(sentiment: string): string {
  switch (sentiment.toUpperCase()) {
    case 'BULLISH':
      return 'text-terminal-green';
    case 'BEARISH':
      return 'text-terminal-red';
    case 'NEUTRAL':
      return 'text-terminal-yellow';
    default:
      return 'text-gray-400';
  }
}

/**
 * Get impact score color
 */
export function getImpactColor(score: number): string {
  if (score >= 7) return 'bg-terminal-red';
  if (score >= 5) return 'bg-terminal-yellow';
  return 'bg-terminal-green';
}

/**
 * Validate ticker symbol format
 */
export function isValidTicker(symbol: string): boolean {
  return /^[A-Z]{4}$/.test(symbol);
}

/**
 * Sleep utility for delays
 */
export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Safely parse JSON with fallback
 */
export function safeJsonParse<T>(json: string, fallback: T): T {
  try {
    return JSON.parse(json) as T;
  } catch {
    return fallback;
  }
}
