import axios from 'axios';
import * as cheerio from 'cheerio';
import Parser from 'rss-parser';

const rssParser = new Parser();

export interface NewsItem {
  title: string;
  content: string;
  url: string;
  source: string;
  publishedAt: Date;
}

/**
 * Fetches news from Indonesian financial news sources
 */
export async function fetchIDXNews(tickerSymbol: string): Promise<NewsItem[]> {
  const allNews: NewsItem[] = [];

  try {
    // Fetch from multiple sources in parallel
    const [kontan, bisnis, cnbc] = await Promise.allSettled([
      fetchKontanNews(tickerSymbol),
      fetchBisnisNews(tickerSymbol),
      fetchCNBCIndonesiaNews(tickerSymbol),
    ]);

    if (kontan.status === 'fulfilled') allNews.push(...kontan.value);
    if (bisnis.status === 'fulfilled') allNews.push(...bisnis.value);
    if (cnbc.status === 'fulfilled') allNews.push(...cnbc.value);

    // Sort by published date, most recent first
    return allNews.sort((a, b) => b.publishedAt.getTime() - a.publishedAt.getTime());
  } catch (error) {
    console.error('Error fetching news:', error);
    return allNews;
  }
}

/**
 * Fetch news from Kontan (kontan.co.id)
 */
async function fetchKontanNews(tickerSymbol: string): Promise<NewsItem[]> {
  try {
    const searchUrl = `https://www.kontan.co.id/search/?q=${tickerSymbol}`;
    const response = await axios.get(searchUrl, {
      timeout: 10000,
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      },
    });

    const $ = cheerio.load(response.data);
    const news: NewsItem[] = [];

    // Parse search results (this is a simplified example)
    $('.list-berita article').each((_, element) => {
      const $el = $(element);
      const title = $el.find('h1, h2, h3').text().trim();
      const url = $el.find('a').attr('href') || '';
      const dateText = $el.find('.font-gray').text().trim();

      if (title && url) {
        news.push({
          title,
          content: title, // Will be enriched later
          url: url.startsWith('http') ? url : `https://www.kontan.co.id${url}`,
          source: 'Kontan',
          publishedAt: parseIndonesianDate(dateText) || new Date(),
        });
      }
    });

    return news.slice(0, 10);
  } catch (error) {
    console.error('Error fetching Kontan news:', error);
    return [];
  }
}

/**
 * Fetch news from Bisnis Indonesia
 */
async function fetchBisnisNews(tickerSymbol: string): Promise<NewsItem[]> {
  try {
    const searchUrl = `https://www.bisnis.com/search?q=${tickerSymbol}`;
    const response = await axios.get(searchUrl, {
      timeout: 10000,
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      },
    });

    const $ = cheerio.load(response.data);
    const news: NewsItem[] = [];

    $('.search-item').each((_, element) => {
      const $el = $(element);
      const title = $el.find('h2, .title').text().trim();
      const url = $el.find('a').attr('href') || '';
      const snippet = $el.find('p').text().trim();

      if (title && url) {
        news.push({
          title,
          content: snippet || title,
          url: url.startsWith('http') ? url : `https://www.bisnis.com${url}`,
          source: 'Bisnis Indonesia',
          publishedAt: new Date(),
        });
      }
    });

    return news.slice(0, 10);
  } catch (error) {
    console.error('Error fetching Bisnis news:', error);
    return [];
  }
}

/**
 * Fetch news from CNBC Indonesia
 */
async function fetchCNBCIndonesiaNews(tickerSymbol: string): Promise<NewsItem[]> {
  try {
    const searchUrl = `https://www.cnbcindonesia.com/search?query=${tickerSymbol}`;
    const response = await axios.get(searchUrl, {
      timeout: 10000,
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      },
    });

    const $ = cheerio.load(response.data);
    const news: NewsItem[] = [];

    $('.list_news article').each((_, element) => {
      const $el = $(element);
      const title = $el.find('h4, .title').text().trim();
      const url = $el.find('a').attr('href') || '';
      const snippet = $el.find('.text').text().trim();

      if (title && url) {
        news.push({
          title,
          content: snippet || title,
          url: url.startsWith('http') ? url : `https://www.cnbcindonesia.com${url}`,
          source: 'CNBC Indonesia',
          publishedAt: new Date(),
        });
      }
    });

    return news.slice(0, 10);
  } catch (error) {
    console.error('Error fetching CNBC Indonesia news:', error);
    return [];
  }
}

/**
 * Fetch corporate disclosures from IDX
 */
export async function fetchIDXDisclosures(tickerSymbol: string): Promise<NewsItem[]> {
  try {
    // IDX disclosure page
    const url = `https://www.idx.co.id/en/listed-companies/company-information/`;
    
    // Note: In production, you'd need to implement proper IDX API integration
    // This is a placeholder for the structure
    
    return [];
  } catch (error) {
    console.error('Error fetching IDX disclosures:', error);
    return [];
  }
}

/**
 * Utility function to parse Indonesian date formats
 */
function parseIndonesianDate(dateStr: string): Date | null {
  try {
    // Handle formats like "1 jam lalu", "2 hari lalu", etc.
    const now = new Date();
    
    if (dateStr.includes('jam lalu')) {
      const hours = parseInt(dateStr);
      return new Date(now.getTime() - hours * 60 * 60 * 1000);
    }
    
    if (dateStr.includes('hari lalu')) {
      const days = parseInt(dateStr);
      return new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
    }
    
    if (dateStr.includes('menit lalu')) {
      const minutes = parseInt(dateStr);
      return new Date(now.getTime() - minutes * 60 * 1000);
    }
    
    // Try to parse as standard date
    const parsed = new Date(dateStr);
    if (!isNaN(parsed.getTime())) {
      return parsed;
    }
    
    return null;
  } catch {
    return null;
  }
}

/**
 * Fetch article full content from URL
 */
export async function fetchArticleContent(url: string): Promise<string> {
  try {
    const response = await axios.get(url, {
      timeout: 10000,
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      },
    });

    const $ = cheerio.load(response.data);
    
    // Remove unwanted elements
    $('script, style, nav, header, footer, .ads').remove();
    
    // Try to find main content
    const content = $('article, .article-content, .content, main')
      .text()
      .trim()
      .replace(/\s+/g, ' ')
      .substring(0, 5000); // Limit content length

    return content || '';
  } catch (error) {
    console.error('Error fetching article content:', error);
    return '';
  }
}
