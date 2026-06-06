// Shared frontend dedup for all news sections (High-Impact Saham,
// Berita Makro & Pasar, ticker page feed). Two passes:
//   1. Topic limit  — max 2 articles per high-frequency topic keyword
//   2. Word overlap — skip any article sharing 4+ significant words with a kept one
//
// Runs client/render-side as a last line of defence on top of the
// DB-level inter-batch dedup in backend/workers/dedup.py.

const TOPIC_KEYWORDS = [
  'rupiah', 'dolar as', 'ihsg',
  'dividen', 'rights issue', 'rups',
  'merger', 'akuisisi',
];

export function dedupArticles<T extends { title: string }>(articles: T[]): T[] {
  const kept: T[] = [];
  const topicCount: Record<string, number> = {};

  for (const article of articles) {
    const titleLower = article.title.toLowerCase();

    // Topic limit: max 2 per topic
    const matchedTopic = TOPIC_KEYWORDS.find(kw => titleLower.includes(kw));
    if (matchedTopic) {
      if ((topicCount[matchedTopic] || 0) >= 2) continue;
      topicCount[matchedTopic] = (topicCount[matchedTopic] || 0) + 1;
    }

    // Word similarity: skip if 4+ significant words match a kept article
    const words = new Set(titleLower.split(/\s+/).filter(w => w.length > 3));
    const isDup = kept.some(k => {
      const kWords = new Set(
        k.title.toLowerCase().split(/\s+/).filter((w: string) => w.length > 3)
      );
      return Array.from(words).filter(w => kWords.has(w)).length >= 4;
    });

    if (!isDup) kept.push(article);
  }
  return kept;
}
