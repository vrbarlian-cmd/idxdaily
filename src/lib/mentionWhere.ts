// Shared ticker-mention filter used by the ticker page, the sitemap and the
// homepage trending strip, so "what counts as an article for this ticker" is
// defined in exactly one place.

/**
 * Filter for mentions WITHOUT a ticker constraint (bulk queries / groupBy).
 *
 * INVARIANT: only enriched articles (aiSummary IS NOT NULL) — unenriched ones
 * would otherwise show the DB-default NEUTRAL/5.0 placeholder values.
 *
 * INVARIANT: never category='SKIP'. enrich.py's relevance pre-filter sets
 * category=SKIP *and* a placeholder aiSummary ("[filtered: not market
 * relevant]"), which passes the aiSummary check, so SKIP must be excluded
 * separately.
 */
export function mentionFilter(
  sentimentFilter: string | undefined,
  dateGte: Date | null,
  dateLt: Date | null,
  includeMacro: boolean,
) {
  const dateFilter: Record<string, unknown> = {};
  if (dateGte) dateFilter.gte = dateGte;
  if (dateLt) dateFilter.lt = dateLt;
  const hasDateFilter = Object.keys(dateFilter).length > 0;

  const validSentiment =
    !!sentimentFilter && ['BULLISH', 'BEARISH', 'NEUTRAL'].includes(sentimentFilter);

  // Match-type branch: high/medium ticker matches OR (optionally) macro-impact mentions.
  const matchTypeOr: Record<string, unknown>[] = [
    { matchConfidence: { in: ['high', 'medium'] } },
    ...(includeMacro ? [{ matchType: 'macro_impact' as const }] : []),
  ];

  // Sentiment branch — applied at the TOP level (AND) so it constrains BOTH
  // ticker-match AND macro-impact rows. Falls back to article.sentiment when
  // the mention's own sentiment is null.
  const sentimentAnd = validSentiment
    ? [{
        OR: [
          { sentiment: sentimentFilter },
          { sentiment: null, article: { sentiment: sentimentFilter } },
        ],
      }]
    : [];

  return {
    article: hasDateFilter
      ? { publishedAt: { ...dateFilter, not: null as null }, aiSummary: { not: null }, category: { not: 'SKIP' } }
      : { publishedAt: { not: null as null }, aiSummary: { not: null }, category: { not: 'SKIP' } },
    AND: [
      { OR: matchTypeOr },
      ...sentimentAnd,
    ],
  };
}

/** Same filter, constrained to one ticker. */
export function buildMentionWhere(
  tickerId: string,
  sentimentFilter: string | undefined,
  dateGte: Date | null,
  dateLt: Date | null,
  includeMacro: boolean,
) {
  return { tickerId, ...mentionFilter(sentimentFilter, dateGte, dateLt, includeMacro) };
}
