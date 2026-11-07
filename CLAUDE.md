# DailyIHSG — notes for Claude

DailyIHSG (https://dailyihsg.com) is an Indonesian stock-market news site with an
IHSG Fear & Greed Index. The owner is not a programmer: explain things in plain,
simple English (they sometimes write in Indonesian/English mix).

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
- Finish by reporting the new Fear & Greed score, its label, and which
  components moved the most.

Fear & Greed labels: <25 Extreme Fear, <45 Fear, <55 Neutral, <75 Greed, ≥75 Extreme Greed.

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
- Stage specific files only (never `git add -A`). Run `git pull` before starting work.

## Quick reference

- Main article table is `articles` (Prisma model `news`).
- Backend: Python 3.11 in `backend/` (workers + scripts). Frontend: Next.js 14 in `src/`.
- Primary news ingester is a DigitalOcean VM; the website runs on Vercel.
