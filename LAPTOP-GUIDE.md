# DailyIHSG — Laptop Guide (no coding needed)

Use this when you are away from the home PC and want to do the daily
market-data update from your laptop. Claude Code does all the technical work;
you only open the app and paste things.

---

## Part 1 — One-time setup (do this only once per laptop)

1. **Install 3 programs** (download from their official sites, click Next → Next → Finish):
   - **Git** — https://git-scm.com/download/win
   - **Python 3.11** — https://www.python.org/downloads/release/python-3119/
     (on the first install screen, tick **"Add python.exe to PATH"**)
   - **Claude desktop app** — https://claude.ai/download (sign in with your account)

2. **Get the project onto the laptop.** Open the Claude app → **Code** tab →
   choose your **Documents** folder → start a session and paste:

   ```
   Clone https://github.com/vrbarlian-cmd/idxdaily.git into this folder,
   then install the Python requirements (pip install -r requirements.txt).
   Tell me in plain words if anything fails.
   ```

3. **Add the password file.**
   - Open the email you sent yourself with `dailyihsg-env.txt`, download it.
   - Move it into the new **Documents\idxdaily** folder.
   - Rename it to exactly **`.env.local`** (Windows may warn about changing the
     extension — click Yes).
   - Delete that email from **Sent**, **Inbox** and **Trash**.

4. **First session in the project.** In the Claude app → **Code** → choose the
   **idxdaily** folder → new session → paste the **First-time prompt** below.

5. **If a browser window asks you to sign in to GitHub**, sign in with your usual
   account. If Claude asks for a name/email "for git commits", give your name and
   email. Both happen only once.

### First-time prompt (paste once)

```
This is the DailyIHSG repo. I'm on my laptop (my home PC is off).
First run `git pull origin main`, then read CLAUDE.md fully and follow it.
Check that .env.local exists in this folder (don't print its contents) and
that `pip install -r requirements.txt` is done; if anything is missing,
tell me in plain words what to do.

Then do my daily data entry. I'll paste the IDX data (IHSG close, domestic
and foreign buy/sell in billion IDR, and breadth as a | b | c | d | e).
For each date, oldest first:
- foreign net = foreign buy - foreign sell
- run set_foreign_flow (with --ihsg), set_domestic_flow, set_market_breadth
- check every output for Traceback / Error / saved
If any date is not today: back up fear_greed_index with backup_table, then
run compute_index --backfill over those dates, then compute_index for today.
Flag anything unusual and ask me before guessing.
Finish with a table: date, IHSG, foreign net, breadth, F&G score, label,
and which components moved most.
```

---

## Part 2 — Every day (the routine)

1. Open the Claude app → **Code** → choose the **idxdaily** folder → **new session**.
2. Paste **only your IDX data**, the same as always. Example:

   ```
   46 | 96 | 239 | 219 | 345

   Friday, 13 November 2026
   IDX Composite Index (IHSG) Current Value: 5,344.406
   ...
   Domestic Investor | Buy: 8,152 billion IDR | Sell: 7,922 billion IDR
   Foreign Investor | Buy: 4,221 billion IDR | Sell: 4,450 billion IDR
   ```

   (Several days at once is fine — put each day's breadth line with its date.)
3. Wait 1–5 minutes. Claude pulls the latest code, enters the data, recalculates
   Fear & Greed, and shows you a result table.
4. Done. The website shows the new numbers right away. **Nothing to push.**

If Claude ever seems to skip a step, put this line above your data:

```
Enter this data following CLAUDE.md.
```

---

## Part 3 — Common questions

**Do I need to push to GitHub?**
No. Daily data goes straight into the database, not into files, so there is
nothing to push. If you ask Claude to change the website or a script, Claude
pushes automatically (CLAUDE.md tells it to). To double-check, type:
`Is everything pushed to GitHub?`

**Do I need Remote Control?**
No. Remote Control is for steering a session on a computer that is switched on.
Your home PC is off, so the laptop runs its own session.

**Can I continue the same chat from the PC?**
No — chats stay on the computer where they ran. That's fine: CLAUDE.md and this
guide hold everything Claude needs, and every session pulls the latest code.

**What can't the laptop do?**
- Changes to the news server (DigitalOcean). Its key is only on the home PC.
  Claude will push the change and remind you to copy it to the server from the PC.
- Running the 15-minute news collector. Never set it up on the laptop — two
  copies double the database cost.

**Something went wrong / red error text?**
Don't fix it yourself. Copy the message to Claude and ask:
`What happened, in plain words, and is the data saved?`

**Back on the home PC?**
Just open the session there as usual. Claude pulls first, so both computers
stay in sync.
