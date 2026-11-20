# DailyIHSG — notes for Claude

DailyIHSG (https://dailyihsg.com) is an Indonesian stock-market news site with an
IHSG Fear & Greed Index. The owner is not a programmer: explain things in plain,
simple English (they sometimes write in Indonesian/English mix).

## Git sync (ALWAYS — the owner works from both a home PC and a laptop)

- **At the start of every session, and whenever the owner comes back to continue
  a chat**, run `git pull origin main` in this folder before doing anything
  else, and tell the owner in one line whether anything new came in. If the
  pull fails (conflict, uncommitted changes), stop and explain in plain words.
- **After every change to files in this repo**, commit and push right away
  (`git push origin main`) without being asked, and tell the owner it was
  pushed. Stage only the files you changed (never `git add -A`), and never
  commit `.env.local` or anything with passwords/keys.
- Pushing to `main` makes Vercel rebuild the live website. For website (UI)
  changes, check them on the local dev server first, then push.
- Daily data entry only writes to the database, not to files, so it needs no push.

## Daily data entry (the main job on a laptop)

The owner pastes daily market data from idx.co.id: IHSG close, Foreign Buy/Sell,
Domestic Buy/Sell (billion IDR) and market breadth (advance/decline). Enter it
into the Neon database with the scripts below.

Setup facts:
- Run everything from the repo root with `python` (not `python3`).
- The scripts load `.env.local` themselves (it holds `DATABASE_URL`). It is
  gitignored and copied in by hand. Never print, commit or share its contents.
- If `.env.local` is missing, stop and tell the owner to copy it from the home PC
  by USB stick.

Per trading date (YYYY-MM-DD), compute foreign net = foreign buy − foreign sell, then:

```
python -m backend.scripts.set_foreign_flow --value <net> --buy-total <fbuy> --sell-total <fsell> --ihsg <close> --date YYYY-MM-DD
python -m backend.scripts.set_domestic_flow --buy <dbuy> --sell <dsell> --date YYYY-MM-DD
python -m backend.scripts.set_market_breadth --advance A --decline D --total 963 --date YYYY-MM-DD
```

Rules:
- Each call takes ~20–60 s because it recomputes the Fear & Greed index afterwards.
  Run them one after another, never in parallel, and never two dates at once.
- Check each output for `Traceback`, `Error` and `saved`.
- When several dates are pasted, enter them oldest first.
- If breadth is missing, enter the rest and ask the owner for it.
- Flag numbers that look unusual (e.g. a huge flow or a big IHSG move) and ask
  the owner to confirm. They are sometimes real (Oct 7 2026 domestic ~32 T IDR
  and the Oct 16 2026 −11.57% crash were both real).
- **The entry scripts only recompute TODAY's Fear & Greed row.** Whenever you
  enter a date that is not today (e.g. several pasted days at once), afterwards:
  1. `python -m backend.scripts.backup_table fear_greed_index`
  2. `python -m backend.workers.compute_index --backfill --from <oldest entered date> --to <newest entered date>`
  3. `python -m backend.workers.compute_index` (refreshes today's live row)
- Finish by reporting the new Fear & Greed score, its label, and which
  components moved the most (read `components_json` of `fear_greed_index`:
  a list of {id, label, score, raw_label}; compare with the previous day).
- Breadth input: the owner pastes 5 numbers `a | b | c | d | e` (biggest losers
  → biggest gainers); decline = a+b, stable = c, advance = d+e, total = sum (945 lately).
- Weekend rows in `fear_greed_index` are written by the live run and are not
  touched by `--backfill` (trading days only). That is expected.

Fear & Greed labels: <25 Extreme Fear, <45 Fear, <55 Neutral, <75 Greed, ≥75 Extreme Greed.

## Adding an important article by hand

When the owner pastes a news link (often seen first on WhatsApp) and asks to put
it on the site:

```
python -m backend.scripts.add_article --url <link> --dry-run   # check first
python -m backend.scripts.add_article --url <link>
```

- It detects tickers like the collector does; with none it is saved as market news.
- If the page can't be read (paywall/blocked), add `--title "..."` and `--summary "..."`
  from what the owner pasted.
- The AI summary/impact score are added by the VM's next run (every 15 min in
  market hours); only then does it show on the website. No push needed (DB only).
- Kontan Insight (insight.kontan.co.id) is collected automatically on the VM
  since 2026-11-20; regular Kontan/Detik/CNBC Indonesia/Bisnis.com are only
  collected by the home PC (they block the VM).

## Do NOT do these

- Do not set up any scheduled task / Task Scheduler job on this machine. Only the
  home PC runs the 15-minute news collector (`scripts/run_ingest.bat`); a second
  copy would double the database cost.
- Do not run `backend.workers.sync_market` — it overwrites the manually entered IHSG closes.
- Do not run `vercel deploy`. The website deploys only by `git push origin main`,
  and only when the owner asks.
- Do not use `backend/scripts/backfill_fear_greed.py` (old method). To recompute
  history use `python -m backend.workers.compute_index --backfill --from YYYY-MM-DD --to YYYY-MM-DD`,
  after backing up the `fear_greed_index` table.
- Stage specific files only (never `git add -A`).

## Quick reference

- Main article table is `articles` (Prisma model `news`).
- Backend: Python 3.11 in `backend/` (workers + scripts). Frontend: Next.js 14 in `src/`.
- Primary news ingester is a DigitalOcean VM; the website runs on Vercel.
- The VM's SSH key (`~/.ssh/dailyihsg_do`) exists only on the home PC. From the
  laptop you cannot deploy to the VM: commit + push the change and tell the
  owner it must be copied to the VM from the home PC. Gemini enrichment also
  runs only on the VM (the Gemini key is not in `.env.local`).
- USD/IDR (`usdidr_daily`, feeds the "Rupiah Stress" component) comes from ECB
  rates via `backend/workers/sync_usdidr.py` (VM cron, weekdays 18:05 UTC).
  Yahoo IDR=X daily closes are often corrupt (3-4% below the day's low), so
  Yahoo is only a guarded fallback. If Rupiah Stress swings wildly, compare
  `usdidr_daily` with ECB, repair with `python -m backend.workers.sync_usdidr --days N`
  (backup the table first), then backfill Fear & Greed.
- Back up any table before bulk changes: `python -m backend.scripts.backup_table <table>`
  (writes to `logs/`, which is gitignored).
