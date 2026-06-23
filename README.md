# Workana Scraping Bot

A Python bot that monitors [Workana](https://www.workana.com) for new job postings, filters by freshness and competition, and optionally sends notifications to Discord.

## Features

- **Scraping** – Fetches IT/programming jobs from Workana (`category=it-programming`).
- **Smart filtering** – Keeps only jobs posted **≤1 hour ago** with **≤10 bids** (low competition).
- **Seen tracking** – Stores the last 50 seen job URLs in `seen_jobs.dat` so only new jobs are reported.
- **Console output** – Colored output with title, budget, posted time, bid count, URL, and skills.
- **Discord** – Optional webhook notifications with embed (author, budget, posted, bids, country, skills).
- **Modes** – Single run or continuous with configurable interval.

## Requirements

- Python 3.7+
- Dependencies in `requirements.txt`

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/pro-cat33/workana-scraping-bot.git
   cd workana-scraping-bot
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

### Environment variables (optional)

Create a `.env` file in the project root (do not commit it):

```env
# Discord webhook URL for the it-programming category (required for Discord mode)
DISCORD_WEBHOOK_IT_PROGRAMMING=https://discord.com/api/webhooks/...
# Optional: Discord user ID to @mention on new jobs
JUPITER_DISCORD_ID=your_discord_user_id
```

### Discord webhook

To send jobs to Discord, create a webhook in Discord (Server Settings → Integrations → Webhooks) and put its URL in `DISCORD_WEBHOOK_IT_PROGRAMMING` in your `.env`. The bot reads it from the environment, so the secret never lives in source.

## Usage

| Command | Description |
|--------|-------------|
| `python main.py` | Single run: scrape once and print new jobs. |
| `python main.py --continuous` or `-c` | Run in a loop (default interval: 300 seconds). |
| `python main.py --discord` or `-d` | Send new jobs to Discord; single run. |
| `python main.py -d -c` | Discord + continuous (interval: 60 seconds). |
| `python main.py -c --interval=60` | Continuous with 60-second interval. |

### Windows quick start

Double-click `start.bat` or run:

```bash
start.bat
```

This runs the bot in **Discord + continuous** mode (`main.py -d -c`).

## Output

- **Console**: Job title, budget, posted time, bids, URL, and skills.
- **Discord**: Embed with title (link), author, budget, posted, bids, country, skills.

## Files

| File | Purpose |
|------|--------|
| `main.py` | Scraper, filters, Discord logic, CLI. |
| `requirements.txt` | Python dependencies. |
| `start.bat` | Runs `main.py -d -c` on Windows. |
| `.env` | Optional env vars (not in repo). |
| `seen_jobs.dat` | Last 50 seen job URLs (not in repo). |

## Notes

- The bot uses a browser-like `User-Agent` and respects the page structure; if Workana changes their HTML/JSON, parsing may need updates.
- Discord rate limits apply; the default 60-second interval in Discord mode helps avoid hitting them and reduces the risk of Workana throttling your IP.
