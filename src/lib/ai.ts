import OpenAI from 'openai';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

export type Sentiment = 'BULLISH' | 'BEARISH' | 'NEUTRAL';

export interface NewsAnalysis {
  aiSummary: string;
  sentiment: Sentiment;
  impactScore: number;
  category: string;
}

export interface EarlySignalAnalysis {
  isSignal: boolean;
  signalType?: string;
  confidence?: number;
  reasoning?: string;
  sentiment?: Sentiment;
}

/**
 * Analyzes news and generates Bloomberg-style summary with sentiment
 */
export async function analyzeNews(
  tickerSymbol: string,
  tickerName: string,
  title: string,
  content: string,
  sector?: string
): Promise<NewsAnalysis> {
  const prompt = `You are a professional financial analyst writing for Bloomberg Terminal.

Analyze this news about ${tickerName} (${tickerSymbol}), an Indonesian stock in the ${sector || 'market'}.

News Title: ${title}
News Content: ${content}

Provide:
1. A 2-3 sentence professional summary focusing on stock price and fundamental impact
2. Sentiment: BULLISH (positive for stock), BEARISH (negative), or NEUTRAL
3. Impact score (0-10): How significant is this news for the stock price?
4. Category: CORPORATE, FINANCIAL, MACRO, REGULATORY, SECTOR, or DISCLOSURE

Respond in JSON format:
{
  "summary": "Your 2-3 sentence Bloomberg-style summary here",
  "sentiment": "BULLISH|BEARISH|NEUTRAL",
  "impactScore": 7.5,
  "category": "CORPORATE",
  "reasoning": "Brief explanation of sentiment and impact"
}

Be concise, professional, and focus on market implications. Do not fabricate facts.`;

  try {
    const response = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      messages: [
        {
          role: 'system',
          content: 'You are a Bloomberg Terminal analyst specializing in Indonesian equities. Provide accurate, concise financial analysis.',
        },
        {
          role: 'user',
          content: prompt,
        },
      ],
      response_format: { type: 'json_object' },
      temperature: 0.3,
    });

    const result = JSON.parse(response.choices[0].message.content || '{}');

    return {
      aiSummary: result.summary || 'Summary unavailable',
      sentiment: (result.sentiment || 'NEUTRAL') as Sentiment,
      impactScore: Math.min(10, Math.max(0, result.impactScore || 5)),
      category: result.category || 'GENERAL',
    };
  } catch (error) {
    console.error('Error analyzing news:', error);
    return {
      aiSummary: 'AI analysis unavailable. Please check the original source.',
      sentiment: 'NEUTRAL',
      impactScore: 5,
      category: 'GENERAL',
    };
  }
}

/**
 * Detects early signals from various data sources
 */
export async function detectEarlySignal(
  tickerSymbol: string,
  tickerName: string,
  dataType: 'filing' | 'commodity' | 'macro' | 'regulatory',
  data: string,
  context?: string
): Promise<EarlySignalAnalysis> {
  const prompt = `You are an expert at detecting early market signals before they are fully priced in.

Analyze this ${dataType} data for ${tickerName} (${tickerSymbol}):

Data: ${data}
${context ? `Context: ${context}` : ''}

Determine if this represents an early signal that the market may not have fully priced in yet.

Respond in JSON format:
{
  "isSignal": true|false,
  "signalType": "FILING|COMMODITY|MACRO|REGULATORY|INSIDER",
  "confidence": 0.85,
  "reasoning": "Explain why this is or isn't a signal",
  "sentiment": "BULLISH|BEARISH|NEUTRAL",
  "keyInsight": "The main insight in one sentence"
}

Only identify genuine signals. Be conservative and honest about uncertainty.`;

  try {
    const response = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      messages: [
        {
          role: 'system',
          content: 'You are a market signal detection expert. Identify early indicators that markets may not have fully priced in. Do not hallucinate.',
        },
        {
          role: 'user',
          content: prompt,
        },
      ],
      response_format: { type: 'json_object' },
      temperature: 0.2,
    });

    const result = JSON.parse(response.choices[0].message.content || '{}');

    return {
      isSignal: result.isSignal || false,
      signalType: result.signalType,
      confidence: result.confidence ? Math.min(1, Math.max(0, result.confidence)) : undefined,
      reasoning: result.reasoning,
      sentiment: result.sentiment as Sentiment,
    };
  } catch (error) {
    console.error('Error detecting early signal:', error);
    return {
      isSignal: false,
    };
  }
}

/**
 * Batch analyze multiple news items
 */
export async function batchAnalyzeNews(
  items: Array<{
    tickerSymbol: string;
    tickerName: string;
    title: string;
    content: string;
    sector?: string;
  }>
): Promise<NewsAnalysis[]> {
  const analyses = await Promise.all(
    items.map((item) =>
      analyzeNews(
        item.tickerSymbol,
        item.tickerName,
        item.title,
        item.content,
        item.sector
      )
    )
  );

  return analyses;
}

/**
 * Generate a market impact summary for a ticker
 */
export async function generateMarketImpactSummary(
  tickerSymbol: string,
  tickerName: string,
  recentNews: Array<{ title: string; sentiment: string; impactScore: number }>
): Promise<string> {
  if (recentNews.length === 0) {
    return 'No recent news available for analysis.';
  }

  const prompt = `You are a Bloomberg Terminal analyst. Provide a brief market impact summary for ${tickerName} (${tickerSymbol}) based on recent news.

Recent news items:
${recentNews.map((n, i) => `${i + 1}. ${n.title} [${n.sentiment}, Impact: ${n.impactScore}/10]`).join('\n')}

Write 2-3 sentences summarizing the overall sentiment and key drivers affecting this stock. Be professional and concise.`;

  try {
    const response = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      messages: [
        {
          role: 'system',
          content: 'You are a Bloomberg Terminal analyst providing concise market summaries.',
        },
        {
          role: 'user',
          content: prompt,
        },
      ],
      temperature: 0.4,
      max_tokens: 150,
    });

    return response.choices[0].message.content || 'Summary unavailable.';
  } catch (error) {
    console.error('Error generating market impact summary:', error);
    return 'Summary generation failed.';
  }
}
