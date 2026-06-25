#!/usr/bin/env python3
"""
AI enrichment worker — writes ai_summary, sentiment, impact_score, category.

Requires GEMINI_API_KEY in .env; exits cleanly if absent.

Usage (from project root):
  python -m backend.workers.enrich --batch 5
  python -m backend.workers.enrich --batch 5 --ticker BBRI

Or (from backend/):
  python -m workers.enrich --batch 5
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone

# Windows cp1252 stdout cannot encode Indonesian text (curly quotes, ellipsis,
# en-dash, etc.) that appears in article titles printed during enrichment.
# Reconfigure stdout to UTF-8 with replacement so print() never raises
# UnicodeEncodeError regardless of article content.
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

from ._db import get_conn


# ---------------------------------------------------------------------------
# Async DB helpers  (asyncpg — $1 $2 $3 placeholders, snake_case columns)
# ---------------------------------------------------------------------------

async def fetch_unenriched(conn, limit: int, ticker: str | None, force: bool = False) -> list[dict]:
    """
    Returns articles needing enrichment. Includes:
    - Articles with a primary ticker (standard enrichment)
    - Articles with ticker_id = NULL (macro articles — macro-impact only)
    """
    null_filter = "" if force else "AND a.ai_summary IS NULL"
    if ticker:
        rows = await conn.fetch(
            f"""
            SELECT a.id, a.title, a.original_summary, a.source,
                   a.ticker_id, t.symbol, t.name, t.sector
            FROM articles a
            JOIN tickers t ON t.id = a.ticker_id
            WHERE t.symbol = $1
              {null_filter}
            ORDER BY a.published_at DESC
            LIMIT $2
            """,
            ticker, limit,
        )
    else:
        # Include both: articles with a primary ticker AND NULL-ticker macro articles
        rows = await conn.fetch(
            f"""
            SELECT a.id, a.title, a.original_summary, a.source,
                   a.ticker_id, a.body,
                   COALESCE(t.symbol, '_MACRO_') AS symbol,
                   COALESCE(t.name,   'Macro News') AS name,
                   t.sector
            FROM articles a
            LEFT JOIN tickers t ON t.id = a.ticker_id
            WHERE 1=1 {null_filter}
            ORDER BY a.published_at DESC
            LIMIT $1
            """,
            limit,
        )
    return [dict(r) for r in rows]


async def save_enrichment(conn, article_id: str, result: dict) -> None:
    await conn.execute(
        """
        UPDATE articles
        SET ai_summary   = $1,
            sentiment    = $2,
            impact_score = $3,
            category     = $4,
            updated_at   = $5
        WHERE id = $6
        """,
        result.get("summary", ""),
        result.get("sentiment", "NEUTRAL"),
        float(result.get("impactScore", 5.0)),
        result.get("category", "GENERAL"),
        datetime.now(timezone.utc),
        article_id,
    )


async def save_mention_enrichment(conn, article_id: str, ticker_id: str, result: dict) -> None:
    """Write per-ticker summary/sentiment/impact into ticker_mentions row."""
    await conn.execute(
        """
        UPDATE ticker_mentions
        SET ai_summary   = $1,
            sentiment    = $2,
            impact_score = $3
        WHERE article_id = $4 AND ticker_id = $5
        """,
        result.get("summary", ""),
        result.get("sentiment", "NEUTRAL"),
        float(result.get("impactScore", 5.0)),
        article_id,
        ticker_id,
    )


def call_gemini_macro_impact(
    api_key: str, row: dict, existing_symbols: list[str], model: str | None = None
) -> list[dict]:
    """
    Run macro-impact analysis on a MACRO/REGULATORY/SECTOR article.
    Returns list of {symbol, sentiment, confidence, impactScore, summary} dicts.
    Only HIGH and MEDIUM confidence tickers are returned.
    """
    from google.genai import types as gtypes
    model = model or DEFAULT_MODEL
    client = _get_client(api_key)

    existing_clause = ""
    if existing_symbols:
        existing_clause = (
            f"\nSaham yang SUDAH disebutkan langsung dalam berita "
            f"(tidak perlu diulang): {', '.join(existing_symbols)}\n"
        )

    # Use full article body when available — gives AI the specific mechanism context
    body = (row.get("body") or "").strip()
    if body:
        content_block = f"Isi Artikel:\n{body[:3500]}"
        context_source = f"body {len(body)}c"
    else:
        snippet = (row.get("original_summary") or row["title"])[:600]
        content_block = f"Ringkasan: {snippet}"
        context_source = "snippet"

    print(f"     [macro-impact] context={context_source}")

    prompt = MACRO_IMPACT_TEMPLATE.format(
        example=_MACRO_EXAMPLE,
        category=row.get("category", "MACRO"),
        title=row["title"],
        content_block=content_block,
        existing_clause=existing_clause,
    )

    last_exc: Exception | None = None
    last_transient = False
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=gtypes.GenerateContentConfig(
                    system_instruction=MACRO_IMPACT_SYSTEM,
                    temperature=0.2,          # lower temp = more consistent ticker IDs
                    response_mime_type="application/json",
                ),
            )
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw.strip())
            tickers = data.get("affected_tickers", [])
            # Keep only HIGH/MEDIUM confidence AND strong connection — weak ones are noise
            kept = [
                t for t in tickers
                if t.get("confidence", "").upper() in ("HIGH", "MEDIUM")
                and t.get("connection_strength", "weak").lower() == "strong"
            ]
            dropped = len(tickers) - len(kept)
            if dropped:
                weak_syms = [t.get("symbol","?") for t in tickers if t not in kept]
                print(f"     [macro-filter] dropped {dropped} weak: {', '.join(weak_syms)}")
            return kept
        except Exception as exc:
            msg = str(exc)
            is_rate = "429" in msg or "EXHAUSTED" in msg
            is_transient = "503" in msg or "UNAVAILABLE" in msg
            last_exc = exc
            last_transient = is_rate or is_transient
            if attempt < 2 and (is_rate or is_transient):
                wait = (30 * (2 ** attempt)) if is_rate else (10 * (2 ** attempt))
                print(f"     [macro-retry {attempt+1}] waiting {wait}s ...")
                time.sleep(wait)
            else:
                break
    if last_transient and model != FALLBACK_MODEL:
        print(f"     [macro-fallback] {model} unavailable → {FALLBACK_MODEL}")
        return call_gemini_macro_impact(api_key, row, existing_symbols, model=FALLBACK_MODEL)
    assert last_exc is not None
    raise last_exc


async def save_macro_impact_mentions(
    conn,
    article_id: str,
    affected: list[dict],
    ticker_map: dict[str, str],
    existing_tids: set[str],
    category: str = "MACRO",
) -> int:
    """
    Insert ticker_mention rows with match_type='macro_impact' for tickers
    identified by the macro-impact analysis that aren't already direct matches.
    Returns count of rows inserted.
    """
    count = 0
    for item in affected:
        symbol = item.get("symbol", "").upper().strip()
        if not symbol or symbol not in ticker_map:
            continue  # Ticker not in our DB — skip
        tid = ticker_map[symbol]
        if tid in existing_tids:
            continue  # Already a direct mention — don't overwrite

        conf = item.get("confidence", "medium").lower()
        await conn.execute(
            """
            INSERT INTO ticker_mentions
              (article_id, ticker_id, match_confidence, match_type,
               ai_summary, sentiment, impact_score)
            VALUES ($1, $2, $3, 'macro_impact', $4, $5, $6)
            ON CONFLICT (article_id, ticker_id) DO UPDATE
              SET match_type   = 'macro_impact',
                  ai_summary   = EXCLUDED.ai_summary,
                  sentiment    = EXCLUDED.sentiment,
                  impact_score = EXCLUDED.impact_score
            """,
            article_id, tid, conf,
            item.get("summary", ""),
            item.get("sentiment", "NEUTRAL"),
            float(item.get("impactScore", 5.0)),
        )
        count += 1
    return count


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "PENTING: Seluruh output field 'summary' WAJIB ditulis dalam Bahasa Indonesia. "
    "Jika Anda menulis dalam Bahasa Inggris, jawaban dianggap salah.\n\n"
    "PENTING: Nama lembaga, merek, dan singkatan internasional (S&P, AT&T, R&D, M&A, dll.) "
    "TIDAK BOLEH diterjemahkan. Tulis persis seperti aslinya. "
    "Contoh: 'S&P' bukan 'SdanP', 'R&D' bukan 'RdanP'.\n\n"
    "Anda adalah analis keuangan profesional yang menulis untuk terminal Bloomberg. "
    "Analisis berita saham Indonesia dan balas HANYA dengan JSON yang valid."
)

# One-shot examples — GOOD vs BAD, ticker-first 2-sentence rule
_EXAMPLE = """\
CONTOH BURUK (jangan lakukan ini):
"IHSG turun ke 6.000-an. BEI menekankan investasi jangka panjang. Bagi BUKA, sentimen netral karena berita lebih berfokus pada kondisi pasar umum."
→ SALAH: kalimat pertama tentang pasar umum, bukan BUKA. Ada 3 kalimat.

CONTOH BENAR (lakukan ini):
"BUKA ikut tertekan saat IHSG ambles ke level 6.000, turun bersama saham teknologi lain. Dampak netral-cenderung-negatif jangka pendek karena pelemahan ini bersifat sentimen pasar, bukan masalah fundamental Bukalapak."
→ BENAR: kalimat 1 langsung sebut BUKA, kalimat 2 jelaskan sebab-akibat. Tepat 2 kalimat.

Contoh lain yang BENAR untuk berita korporasi:
{
  "summary": "BRI mencetak laba bersih Rp 15,9 triliun di Q1 2026, tumbuh 12% YoY dan melampaui estimasi konsensus. Ini sinyal positif bagi BBRI karena membuktikan tekanan NIM tidak separah kekhawatiran pasar, berpotensi memicu revisi naik target harga analis.",
  "sentiment": "BULLISH",
  "impactScore": 8.0,
  "category": "FINANCIAL"
}"""

USER_TEMPLATE = """PENTING: Field 'summary' WAJIB dalam Bahasa Indonesia. Lihat contoh di bawah.

{example}

---
Sekarang analisis berita berikut tentang {name} ({symbol}), saham Indonesia di sektor {sector}.

Judul: {title}
{content_block}

Aturan ketat untuk field 'summary':
- Kalimat 1: Fakta terpenting, langsung dikaitkan dengan emiten {symbol}. \
JANGAN mulai dengan berita pasar umum (IHSG, makro, kurs) — mulai dari yang relevan untuk {symbol}.
- Kalimat 2: Alasan logis mengapa ini bullish/bearish/netral untuk harga saham {symbol}. \
Jelaskan sebab-akibatnya secara sederhana.
- MAKSIMAL 2 kalimat. Berhenti di situ. Jangan tambah kalimat ketiga.
- Ringkasan WAJIB maksimal 240 karakter total. JANGAN pernah memotong kalimat di tengah. \
Pastikan kalimat kedua berakhir dengan tanda titik.
- Pembaca harus paham dampaknya hanya dari kalimat pertama.
- Jika berita makro/pasar: tetap mulai dari dampaknya ke {symbol}, bukan dari kondisi makronya.

Panduan impactScore (GUNAKAN RENTANG PENUH — JANGAN default ke 7.5):
- 9-10: Katalis besar — M&A, kejutan laba besar, regulasi major yang langsung ubah revenue
- 7-8: Berita signifikan perusahaan — dividen, buyback, hasil keuangan notable, kontrak besar
- 4-6: Relevan tapi rutin — update guidance, berita operasional, perkembangan sektoral
- 1-3: Minor/tangensial — berita umum yang sedikit menyebut emiten, dampak tidak langsung
WAJIB: Berikan skor yang BERBEDA untuk setiap artikel sesuai bobot beritanya.

Kembalikan JSON dengan tepat key berikut (summary WAJIB Bahasa Indonesia, TEPAT 2 kalimat):
{{
  "summary": "Kalimat 1: fakta dikaitkan {symbol}. Kalimat 2: sebab-akibat bullish/bearish/netral.",
  "sentiment": "BULLISH" | "BEARISH" | "NEUTRAL",
  "impactScore": <float 0-10>,
  "category": "CORPORATE" | "FINANCIAL" | "MACRO" | "REGULATORY" | "SECTOR" | "DISCLOSURE"
}}"""


# ---------------------------------------------------------------------------
# Macro-impact prompt  (Task 2)
# ---------------------------------------------------------------------------

MACRO_IMPACT_SYSTEM = (
    "Anda adalah analis keuangan senior yang ahli dalam pasar modal Indonesia (IDX/BEI). "
    "Tugas Anda: mengidentifikasi saham IDX yang terdampak SECARA SPESIFIK oleh berita "
    "makroekonomi atau regulasi — hanya jika ada mekanisme dampak yang KONKRET dan LANGSUNG.\n\n"
    "STANDAR KETAT: Dampak 'pasar turun → semua saham turun' adalah NOISE, bukan analisis. "
    "Jika tidak ada mekanisme bisnis yang spesifik menghubungkan berita ke emiten tertentu, "
    "JANGAN sertakan emiten tersebut. Lebih baik mengembalikan 0 emiten daripada mencantumkan "
    "emiten berdasarkan sentimen pasar umum.\n\n"
    "PENTING: Semua field 'summary' WAJIB dalam Bahasa Indonesia. "
    "Framing SELALU sebagai potensi dampak sentimen, BUKAN rekomendasi beli/jual."
)

_MACRO_EXAMPLE = """\
Contoh output untuk berita "Pemerintah larang ekspor batubara 3 bulan":
{
  "affected_tickers": [
    {
      "symbol": "ADRO",
      "sentiment": "BEARISH",
      "confidence": "HIGH",
      "connection_strength": "strong",
      "impactScore": 8.0,
      "summary": "ADRO berpotensi tertekan karena larangan ekspor batubara langsung memangkas volume penjualan ekspor perusahaan. Sebagai produsen batubara thermal terbesar, pembatasan ini secara langsung menekan proyeksi pendapatan ADRO jangka pendek."
    },
    {
      "symbol": "PTRO",
      "sentiment": "BEARISH",
      "confidence": "MEDIUM",
      "connection_strength": "strong",
      "impactScore": 6.5,
      "summary": "PTRO berpotensi terdampak karena sebagai kontraktor tambang batubara, penurunan aktivitas produksi kliennya akan mengurangi permintaan jasa Petrosea. Dampak bergantung pada seberapa besar klien PTRO mengurangi operasi selama larangan berlaku."
    }
  ]
}

Contoh yang DITOLAK (connection_strength: 'weak') — JANGAN masukkan seperti ini:
  ASII: "Pelemahan IHSG di sektor industri dasar menekan ASII" → DITOLAK: tidak ada mekanisme spesifik
  BBCA: "Ketidakpastian pasar menurunkan sentimen investor perbankan" → DITOLAK: berlaku untuk 926 saham
  TLKM: "IHSG turun berdampak negatif ke TLKM" → DITOLAK: horoscope saham, bukan analisis
  UNVR: "Kondisi makro yang lemah menekan daya beli konsumen" → DITOLAK: terlalu generik"""

MACRO_IMPACT_TEMPLATE = """\
{example}

---
Berikut adalah berita {category} yang berpotensi berdampak pada saham-saham IDX:

Judul: {title}
{content_block}
{existing_clause}
ATURAN UTAMA — baca ini dulu sebelum mengidentifikasi emiten:

Hanya sertakan emiten jika ada mekanisme dampak yang SPESIFIK dan LANGSUNG.
Contoh mekanisme yang VALID:
  ✓ Aturan ekspor batu bara → volume penjualan eksportir batubara LANGSUNG berkurang
  ✓ BI naikan suku bunga → NIM bank tertekan (biaya dana naik lebih cepat dari yield kredit)
  ✓ BI naikan suku bunga → KPR makin mahal → permintaan rumah turun → pre-sales pengembang properti tertekan
  ✓ BI naikan suku bunga → cicilan kredit kendaraan naik → penjualan mobil/motor turun (ASII, AUTO)
  ✓ BI turunkan suku bunga → KPR lebih terjangkau → pre-sales properti naik (BSDE, CTRA, SMRA, BKSL)
  ✓ Harga CPO naik → pendapatan produsen sawit naik langsung
  ✓ Royalti nikel dinaikkan → biaya produksi penambang nikel naik

Contoh yang DILARANG (connection_strength: 'weak') — BUANG, jangan masukkan:
  ✗ "IHSG turun jadi saham X turun" — berlaku untuk semua 926 saham, tidak berguna
  ✗ "Sentimen pasar melemah di sektor Y" — terlalu generik
  ✗ "Ketidakpastian makro menekan daya beli" — tidak ada mekanisme spesifik
  ✗ Dampak yang hanya spekulatif atau sangat tidak langsung

Jika dampaknya hanya "pasar turun jadi saham turun", JANGAN sertakan emiten tersebut.
Lebih baik 0 emiten yang tepat daripada 10 emiten berdasarkan sentimen umum.

Untuk setiap emiten yang LOLOS filter di atas:
- connection_strength 'strong' = mekanisme bisnis SPESIFIK yang jelas (harga komoditas → revenue langsung; regulasi → volume/biaya operasi)
- connection_strength 'weak' = hanya sentimen umum/sektoral tanpa mekanisme konkret → JANGAN MASUKKAN
- Confidence HIGH = dampak LANGSUNG ke pendapatan/laba (bisnis utama terkena langsung)
- Confidence MEDIUM = dampak tidak langsung tapi logika bisnisnya jelas dan spesifik

Aturan WAJIB untuk field 'summary' (2 kalimat, Bahasa Indonesia):
- Kalimat 1: Sebutkan MEKANISME SPESIFIK — bagaimana berita ini memengaruhi bisnis emiten secara konkret
- Kalimat 2: Konsekuensi ke pendapatan/laba/operasi — sebab-akibat yang dapat diukur
- JANGAN menulis "sentimen pasar" atau "pelemahan umum" — harus ada mekanisme bisnis nyata
- MAKSIMAL 2 kalimat. Ringkasan WAJIB maksimal 240 karakter total. JANGAN pernah memotong \
kalimat di tengah. Pastikan kalimat kedua berakhir dengan tanda titik.

Kembalikan JSON (hanya affected_tickers, tidak ada field lain):
{{
  "affected_tickers": [
    {{
      "symbol": "KODE4",
      "sentiment": "BULLISH" | "BEARISH" | "NEUTRAL",
      "confidence": "HIGH" | "MEDIUM",
      "connection_strength": "strong" | "weak",
      "impactScore": <float 0-10>,
      "summary": "KODE berpotensi... [mekanisme spesifik]. [konsekuensi ke bisnis]."
    }}
  ]
}}

Panduan sektor (gunakan sebagai referensi untuk emiten yang KURANG terkenal):
- Batubara/coal: PTBA, ADRO, ITMG, HRUM, DOID, BUMI (Bumi Resources), BRMS, GEMS, MBSS
  Kontraktor tambang: PTRO (Petrosea), DSSA, UNTR
- Minyak sawit/CPO: AALI, SSMS, DSNG, SIMP, LSIP, MGRO, BWPT, SMAR
- Nikel/nickel: INCO, ANTM, MBMA, NICL, MDKA, HRUM (nikel)
- Minyak & gas: PGAS, MEDC, ESSA, RELI, AKRA
- Perbankan: BBCA, BBRI, BMRI, BBNI, BJTM, BJBR, BRIS, BTPN, ARTO
  Dampak BI rate: kenaikan suku bunga → NIM tertekan (biaya dana naik > yield kredit); penurunan suku bunga → NIM melebar
- Properti / Pengembang: BSDE, SMRA, CTRA, PWON, LPKR, BKSL (Sentul City), APLN, MKPI
  Dampak BI rate: kenaikan suku bunga → KPR makin mahal → permintaan rumah turun → pre-sales tertekan
  Dampak BI rate: penurunan suku bunga → KPR lebih terjangkau → pre-sales naik → harga tanah meningkat
- Telekomunikasi: TLKM, EXCL, ISAT, FREN
- Retail/consumer: UNVR, ICBP, INDF, MYOR, AMRT, MAPI, ACES, ERAA
- Otomotif: ASII, AUTO, IMAS, SMSM
  Dampak suku bunga: kredit kendaraan lebih mahal → penjualan mobil/motor tertekan
- Infrastruktur/konstruksi: WIKA, PTPP, WSKT, ADHI, JSMR, TOLL

Batasan ketat:
- HANYA kode saham IDX 4 huruf yang valid (emiten Indonesia terdaftar di BEI)
- Maksimal 8 saham (kualitas lebih penting dari kuantitas)
- Jika tidak ada dampak material dengan mekanisme spesifik → kembalikan {{"affected_tickers": []}}
- JANGAN duplikasi saham yang sudah disebutkan langsung dalam berita\
"""

_gemini_client = None

def _get_client(api_key: str):
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


# Paid tier rate limits (with billing enabled):
#   gemini-2.5-flash-lite: 4000 RPM — no artificial delay needed
#   gemini-2.5-flash:      2000 RPM — use --model gemini-2.5-flash to opt in
DEFAULT_MODEL = "gemini-2.5-flash-lite"
FALLBACK_MODEL = "gemini-2.5-flash"  # used when lite returns 503


def call_gemini(api_key: str, row: dict, model: str = DEFAULT_MODEL) -> dict:
    from google.genai import types as gtypes
    client = _get_client(api_key)

    # Use full article body when available; fall back to RSS snippet / title.
    # Body is fetched by fetch_bodies.py and stored in articles.body.
    body = (row.get("body") or "").strip()
    if body:
        # Truncate to ~3000 chars so we stay within prompt limits
        content_block = f"Isi Artikel:\n{body[:3000]}"
    else:
        snippet = (row.get("original_summary") or row["title"])[:800]
        content_block = f"Ringkasan: {snippet}"

    prompt = USER_TEMPLATE.format(
        example=_EXAMPLE,
        name=row["name"], symbol=row["symbol"],
        sector=row.get("sector") or "market",
        title=row["title"],
        content_block=content_block,
    )
    # Retry up to 3 times on transient errors (503) or rate limit (429)
    last_exc: Exception | None = None
    last_transient = False
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=gtypes.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.3,
                    response_mime_type="application/json",
                ),
            )
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            result = json.loads(raw.strip())
            # Safety net: if summary > 240 chars, truncate at last complete sentence
            if isinstance(result.get("summary"), str) and len(result["summary"]) > 240:
                s = result["summary"][:240]
                # Walk back to the last sentence-ending period
                cut = s.rfind(". ")
                if cut == -1:
                    cut = s.rfind(".")
                result["summary"] = s[:cut + 1] if cut != -1 else s
            return result
        except Exception as exc:
            msg = str(exc)
            is_rate = "429" in msg or "EXHAUSTED" in msg
            is_transient = "503" in msg or "UNAVAILABLE" in msg
            last_exc = exc
            last_transient = is_rate or is_transient
            if attempt < 2 and (is_rate or is_transient):
                # Exponential backoff: 30s → 60s → 120s for rate limit; 10s → 20s for 503
                wait = (30 * (2 ** attempt)) if is_rate else (10 * (2 ** attempt))
                print(f"     [retry {attempt+1}/{2}] waiting {wait}s ...")
                time.sleep(wait)
            else:
                break
    if last_transient and model != FALLBACK_MODEL:
        print(f"     [fallback] {model} unavailable → {FALLBACK_MODEL}")
        return call_gemini(api_key, row, model=FALLBACK_MODEL)
    assert last_exc is not None
    raise last_exc


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_batch(limit: int, ticker: str | None, force: bool = False, model: str = DEFAULT_MODEL, delay: float = 0.0) -> None:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print(
            "[enrich] GEMINI_API_KEY is not set.\n"
            "  Get a free key at https://aistudio.google.com/app/apikey\n"
            "  Add GEMINI_API_KEY=<key> to .env, then re-run.\n"
            "Skipping — articles remain at NEUTRAL/5.0 defaults."
        )
        return

    conn = await get_conn()
    try:
        rows = await fetch_unenriched(conn, limit, ticker, force=force)
        label = "articles (force-rewrite)" if force else "unenriched articles"
        print(f"[enrich] {len(rows)} {label}  [model={model}]")

        # Load full ticker map once for macro-impact validation
        ticker_rows = await conn.fetch("SELECT id, symbol FROM tickers")
        ticker_map: dict[str, str] = {r["symbol"]: r["id"] for r in ticker_rows}
        ok = fail = 0
        for row in rows:
            # Fetch all high/medium-confidence mentions for this article
            mention_rows = await conn.fetch(
                """
                SELECT tm.ticker_id, t.symbol, t.name, t.sector
                FROM ticker_mentions tm
                JOIN tickers t ON t.id = tm.ticker_id
                WHERE tm.article_id = $1
                  AND tm.match_confidence IN ('high','medium')
                ORDER BY CASE tm.match_confidence WHEN 'high' THEN 0 ELSE 1 END, t.symbol
                """,
                row["id"],
            )

            if mention_rows:
                mention_list = [dict(m) for m in mention_rows]
                # Ensure primary ticker is always first
                primary_first = sorted(
                    mention_list,
                    key=lambda m: (0 if m["ticker_id"] == row["ticker_id"] else 1, m["symbol"]),
                )
            else:
                # No junction rows — fall back to article's own ticker
                primary_first = [{
                    "ticker_id": row["ticker_id"],
                    "symbol": row["symbol"],
                    "name": row["name"],
                    "sector": row["sector"],
                }]

            primary_tid = row["ticker_id"]
            primary_saved = False
            last_category = "GENERAL"   # track category from primary enrichment

            is_macro_article = (row["symbol"] == "_MACRO_")  # NULL-ticker article

            if is_macro_article:
                # Pure macro article — no direct ticker mentions to enrich.
                # Skip standard per-ticker loop; go straight to macro-impact.
                pass
            else:
                for m in primary_first:
                    enrich_row = {**row, "symbol": m["symbol"], "name": m["name"], "sector": m["sector"]}
                    print(f"  -> [{m['symbol']}] {row['title'][:55]} ...")
                    try:
                        result = call_gemini(api_key, enrich_row, model=model)

                        # Save per-ticker summary into ticker_mentions
                        await save_mention_enrichment(conn, row["id"], m["ticker_id"], result)

                        # Sync the PRIMARY ticker's result to articles (article-level fallback)
                        if m["ticker_id"] == primary_tid and not primary_saved:
                            await save_enrichment(conn, row["id"], result)
                            primary_saved = True
                            last_category = result.get("category", "GENERAL")

                        print(
                            f"     sentiment={result.get('sentiment')}  "
                            f"impact={result.get('impactScore')}  "
                            f"category={result.get('category')}"
                        )
                        ok += 1
                    except Exception as exc:
                        print(f"     [WARN] Gemini failed for {m['symbol']}: {exc}")
                        fail += 1
                    if delay > 0:
                        time.sleep(delay)

            # ── Macro-impact analysis ──────────────────────────────────────────
            # Run for:
            #   (a) Pure macro articles (NULL ticker_id) — always
            #   (b) Direct-ticker articles classified as MACRO/REGULATORY/SECTOR
            run_macro = is_macro_article or last_category in ("MACRO", "REGULATORY", "SECTOR")

            if run_macro:
                existing_symbols = [m["symbol"] for m in primary_first] if not is_macro_article else []
                existing_tids    = {m["ticker_id"] for m in primary_first} if not is_macro_article else set()

                # For macro articles, first infer category from title/snippet via standard call
                macro_row = dict(row)
                if is_macro_article:
                    macro_row["symbol"] = "IHSG"
                    macro_row["name"]   = "Pasar Umum"
                    macro_row["sector"] = "Market"
                    # Classify the article to get its category
                    try:
                        cls_result = call_gemini(api_key, macro_row, model=model)
                        last_category = cls_result.get("category", "MACRO")
                        # Save article-level enrichment
                        await save_enrichment(conn, row["id"], cls_result)
                        ok += 1
                        print(f"  -> [MACRO] {row['title'][:55]} ...")
                        print(f"     category={last_category}  sentiment={cls_result.get('sentiment')}")
                    except Exception as exc:
                        print(f"  -> [MACRO] [WARN] classification failed: {exc}")
                        fail += 1

                # Now run macro-impact to identify affected tickers
                try:
                    macro_row_for_impact = {**row, "category": last_category, "body": row.get("body")}
                    affected = call_gemini_macro_impact(api_key, macro_row_for_impact, existing_symbols, model=model)
                    if affected:
                        n = await save_macro_impact_mentions(
                            conn, row["id"], affected, ticker_map, existing_tids, last_category
                        )
                        syms = [t["symbol"] for t in affected if t.get("symbol") in ticker_map]
                        print(f"     [macro-impact] {n}/{len(affected)} tickers saved: {', '.join(syms[:8])}")
                    else:
                        print(f"     [macro-impact] no affected tickers identified")
                except Exception as exc:
                    print(f"     [macro-impact] [WARN] failed: {exc}")

        total_articles = len(rows)
        print(f"[enrich] Done - {ok} summaries across {total_articles} articles ({fail} failed)")
    finally:
        await conn.close()


async def run_macro_reprocess(limit: int, model: str = DEFAULT_MODEL, delay: float = 0.0) -> None:
    """
    Delete all existing macro_impact mentions and re-run macro-impact analysis
    with the stricter connection_strength filter. Only 'strong' connections survive.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("[macro-reprocess] GEMINI_API_KEY not set. Skipping.")
        return

    conn = await get_conn()
    try:
        ticker_rows = await conn.fetch("SELECT id, symbol FROM tickers")
        ticker_map: dict[str, str] = {r["symbol"]: r["id"] for r in ticker_rows}

        # All macro articles (ticker_id IS NULL), most recent first
        # Include body so the richer context is available for mechanism detection
        rows = await conn.fetch(
            """
            SELECT a.id, a.title, a.original_summary, a.source,
                   a.ticker_id, a.body, COALESCE(a.category, 'MACRO') AS category
            FROM articles a
            WHERE a.ticker_id IS NULL
            ORDER BY a.published_at DESC
            LIMIT $1
            """,
            limit,
        )
        rows = [dict(r) for r in rows]
        print(f"[macro-reprocess] {len(rows)} macro articles  [model={model}]")

        total_before = await conn.fetchval(
            "SELECT COUNT(*) FROM ticker_mentions WHERE match_type = 'macro_impact'"
        )
        print(f"[macro-reprocess] macro_impact mentions BEFORE: {total_before}")

        removed = inserted = skipped = 0
        sample_results: list[dict] = []   # collect up to 3 examples for the report

        for row in rows:
            art_id = row["id"]
            title_short = row["title"][:55]

            # Delete all existing macro_impact mentions for this article
            tag = await conn.execute(
                "DELETE FROM ticker_mentions WHERE article_id = $1 AND match_type = 'macro_impact'",
                art_id,
            )
            n_del = int(tag.split()[-1]) if tag else 0
            removed += n_del

            # Re-run macro-impact with strict prompt + body context
            macro_row = {
                **row,
                "symbol":   "IHSG",
                "name":     "Pasar Umum",
                "sector":   "Market",
                "category": row["category"],
                "body":     row.get("body"),   # None if body not yet fetched
            }
            try:
                affected = call_gemini_macro_impact(api_key, macro_row, [], model=model)
                if affected:
                    n = await save_macro_impact_mentions(
                        conn, art_id, affected, ticker_map, set(), row["category"]
                    )
                    inserted += n
                    syms = [t["symbol"] for t in affected]
                    print(f"  [OK] {title_short}...")
                    print(f"    -> {n} strong mentions: {', '.join(syms)}")
                    if len(sample_results) < 3 and affected:
                        sample_results.append({
                            "title": row["title"],
                            "tickers": affected,
                        })
                else:
                    skipped += 1
                    print(f"  [--] {title_short}... -> 0 (all filtered as weak)")
            except Exception as exc:
                print(f"  [!!] {title_short}... -> WARN: {exc}")

            if delay > 0:
                time.sleep(delay)

        total_after = await conn.fetchval(
            "SELECT COUNT(*) FROM ticker_mentions WHERE match_type = 'macro_impact'"
        )

        print(f"\n[macro-reprocess] ── Summary ──────────────────────────────")
        print(f"  Articles processed : {len(rows)}")
        print(f"  Old mentions deleted: {removed}")
        print(f"  New strong mentions : {inserted}")
        print(f"  Articles -> 0 tickers: {skipped}")
        print(f"  BEFORE: {total_before}  AFTER: {total_after} macro_impact mentions")

        if sample_results:
            print(f"\n[macro-reprocess] ── 3 Example Results ────────────────────")
            for i, ex in enumerate(sample_results, 1):
                print(f"\n  [{i}] {ex['title'][:80]}")
                for t in ex["tickers"][:3]:
                    print(f"      {t.get('symbol')} ({t.get('confidence')}/{t.get('connection_strength')})"
                          f" impactScore={t.get('impactScore')}")
                    print(f"      {t.get('summary','')[:120]}")

    finally:
        await conn.close()


async def run_drain(
    batch: int,
    model: str = DEFAULT_MODEL,
    delay: float = 0.0,
    timeout_min: float = 25.0,
) -> None:
    """
    Loop run_batch() until the unenriched queue is empty or timeout is reached.

    This is the correct way to run enrichment after a large ingest — it guarantees
    zero articles remain with the default NEUTRAL/5.0 placeholder values.

    Invariant goal: after run_drain(), SELECT COUNT(*) FROM articles
    WHERE ai_summary IS NULL should be 0.
    """
    deadline = time.time() + timeout_min * 60
    passes = 0
    print(f"[drain] Starting drain loop (batch={batch}, timeout={timeout_min}m)...")

    while time.time() < deadline:
        conn = await get_conn()
        remaining = await conn.fetchval("SELECT COUNT(*) FROM articles WHERE ai_summary IS NULL")
        await conn.close()

        if remaining == 0:
            print(f"[drain] Queue empty after {passes} pass(es). Invariant satisfied.")
            return

        elapsed_min = (time.time() - (deadline - timeout_min * 60)) / 60
        print(f"[drain] Pass {passes + 1}: {remaining} unenriched articles remaining "
              f"({elapsed_min:.1f}m elapsed)...")
        await run_batch(batch, None, False, model, delay)
        passes += 1

    # Timeout reached — report remaining backlog
    conn = await get_conn()
    remaining = await conn.fetchval("SELECT COUNT(*) FROM articles WHERE ai_summary IS NULL")
    await conn.close()
    print(f"[drain] Timeout after {timeout_min}m. {remaining} articles still unenriched "
          f"(will be caught next cycle).")


def main() -> None:
    parser = argparse.ArgumentParser(description="IDXDaily enrichment worker")
    parser.add_argument("--batch", type=int, default=5)
    parser.add_argument("--ticker", default=None)
    parser.add_argument("--force", action="store_true", help="Re-enrich already-enriched articles")
    parser.add_argument("--drain", action="store_true",
                        help="Loop until all unenriched articles are processed (invariant: 0 remaining)")
    parser.add_argument("--drain-timeout", type=float, default=25.0,
                        help="Max minutes for --drain loop before giving up (default: 25)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini model (default: {DEFAULT_MODEL})")
    parser.add_argument("--delay", type=float, default=0.0, help="Seconds between requests (default: 0 — paid tier has no need)")
    parser.add_argument(
        "--macro-reprocess", action="store_true",
        help="Delete all macro_impact mentions and re-run with stricter connection_strength filter",
    )
    args = parser.parse_args()

    if args.macro_reprocess:
        asyncio.run(run_macro_reprocess(
            args.batch,
            model=args.model,
            delay=args.delay,
        ))
    elif args.drain:
        asyncio.run(run_drain(
            args.batch,
            model=args.model,
            delay=args.delay,
            timeout_min=args.drain_timeout,
        ))
    else:
        asyncio.run(run_batch(
            args.batch,
            args.ticker.upper() if args.ticker else None,
            force=args.force,
            model=args.model,
            delay=args.delay,
        ))


if __name__ == "__main__":
    main()
