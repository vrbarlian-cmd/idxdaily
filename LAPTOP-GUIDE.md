# DailyIHSG — Laptop Guide (no coding needed)

Use this when you are away from the home PC and want to do the daily
market-data update from your laptop. Claude Code does all the technical work;
you only open the app and paste things.

---

## Part 1 — One-time setup (ONE prompt, only once per laptop)

Before you start, do just these 2 things by hand:
1. Install the **Claude desktop app** (https://claude.ai/download) and sign in.
2. Open the email you sent yourself and **download `dailyihsg-env.txt`**
   (it lands in your **Downloads** folder).

Then: Claude app → **Code** tab → choose your **Documents** folder →
**new session** → paste this ONE prompt, with today's IDX data under it:

```
Set up DailyIHSG on this laptop, then enter today's data. I don't code,
so explain anything you need from me in plain words.

1. Check that Git and Python 3.11 are installed. If not, install them
   with winget (Git.Git and Python.Python.3.11) and tell me if I need
   to click anything.
2. Clone https://github.com/vrbarlian-cmd/idxdaily.git into this
   Documents folder (if it already exists, just git pull origin main).
3. Move dailyihsg-env.txt from my Downloads folder into the idxdaily
   folder and rename it to .env.local. Never print its contents.
4. In the idxdaily folder: pip install -r requirements.txt, then read
   CLAUDE.md and LAPTOP-GUIDE.md fully and follow them from now on.
5. Enter the IDX data I paste below following CLAUDE.md (oldest date
   first; backfill if any date is not today), and finish with a table:
   date, IHSG, foreign net, breadth, F&G score, label, and which
   components moved most.

[paste your IDX data here]
```

During setup:
- **If a browser window asks you to sign in to GitHub**, sign in with your
  usual account. If Claude asks for a name/email "for git commits", give your
  name and email. Both happen only once.
- When it's done, **delete that email** from **Sent**, **Inbox** and **Trash**.

---

## Part 2 — Every day (the routine)

Use a **new session every day** (not the setup one): it starts fresh and fast,
and CLAUDE.md gives it all the rules automatically.

1. Open the Claude app → **Code** → choose the **idxdaily** folder
   (Documents\idxdaily — not Documents) → **new session**.
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
