# 🤖 Freelance Job Alerts Bot

Telegram bot that aggregates job postings from multiple sources and sends curated alerts based on user preferences.

## Quick Start

### 1. Get a Bot Token
Message [@BotFather](https://t.me/BotFather) on Telegram: `/newbot`

### 2. Setup (5 min)
```bash
cd freelance-bot
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="your_token_here"
python3 -c "from bot import init_db; init_db()"
```

### 3. Start Bot
```bash
python3 bot.py
```

### 4. Setup Hourly Cron Job
```bash
crontab -e
# Add: 0 * * * * cd /path/to/freelance-bot && TELEGRAM_BOT_TOKEN="token" /path/to/venv/bin/python3 cron_worker.py
```

### 5. Test in Telegram
```
/start
/jobs
/filter
/upgrade
```

## Features

### Free Tier
- 5 jobs per day
- Manual `/jobs` command
- Basic job descriptions

### Premium ($2/month = 200 Telegram Stars)
- Unlimited jobs
- Hourly alerts delivered automatically
- Advanced filtering
- [Coming soon] Skill matching

## Architecture

```
┌─────────────────────────────────────┐
│  User sends /start, /jobs, /upgrade │
├─────────────────────────────────────┤
│  bot.py (long-running Telegram bot) │
│  ├─ Responds to commands            │
│  ├─ Stores user preferences         │
│  └─ Sends manual + alert jobs       │
├─────────────────────────────────────┤
│  SQLite Database                    │
│  ├─ users (preferences, level)      │
│  ├─ jobs (from APIs)                │
│  └─ user_jobs_sent (delivery log)   │
├─────────────────────────────────────┤
│  cron_worker.py (hourly cron job)   │
│  ├─ Fetches from RemoteOK, HN, GH   │
│  ├─ Stores in DB                    │
│  └─ Queues alerts for premium users │
└─────────────────────────────────────┘
```

## File Guide

| File | Purpose |
|------|---------|
| `bot.py` | Main bot - handles Telegram commands |
| `cron_worker.py` | Hourly job fetcher - runs via cron |
| `config.py` | Settings (free tier limit, pricing, etc) |
| `stats.py` | Dashboard - user metrics, revenue, health |
| `DEPLOYMENT.md` | Full setup + troubleshooting guide |

## Management

### Check Stats
```bash
python3 stats.py
```

Shows:
- Total users, free vs premium
- Jobs fetched, by platform
- Revenue (current & projections)
- Alert metrics
- System health

### Troubleshoot
```bash
# Is bot running?
ps aux | grep bot.py

# Check cron logs
tail -f cron_worker.log

# Test job fetcher
TELEGRAM_BOT_TOKEN="token" python3 cron_worker.py

# Check database
sqlite3 freelance_bot.db "SELECT COUNT(*) FROM users;"
```

## Monetization

### Current
- **Free**: 5 jobs/day
- **Premium**: 200 Telegram Stars/month (~$2)

### Future
- Paid integrations (Upwork, Fiverr API access)
- Premium filters (specific skills, budget range)
- Referral bonuses
- Job matching algorithm (ML-based)

## APIs Used (All Free!)

| Source | Limit | Cost |
|--------|-------|------|
| RemoteOK | ~100 jobs/day | Free |
| Hacker News | Unlimited | Free |
| GitHub | 60 req/hr | Free |

## First 10 Paying Users

**Effort estimate**: 2-3 weeks at current pace

### Acquisition Strategy
1. Share in remote work communities (Reddit, FB groups)
2. Upvote on Product Hunt
3. Post in Telegram job/freelance groups
4. Refer friends (1 month free = viral)

### Conversion Funnel
```
Users: 50
   ↓ (try free tier)
Active Users: 20 (40%)
   ↓ (reach 5 jobs/day limit)
Upgrade: 2-3 (10-15% conversion)
```

**To hit 10 paying users**: Need ~100-150 total users (target Q1 2025)

## What You Need to Do

### Daily
- Monitor `stats.py` output
- Check for errors in `cron_worker.log`
- Respond to user support (if any)

### Weekly
- Review conversion metrics
- Test new job sources
- Adjust filters based on user feedback

### Monthly
- Analyze performance
- Adjust pricing if needed
- Plan new features

## Next Steps

1. ✅ Deploy bot to production
2. ✅ Start cron job
3. Share link: `https://t.me/your_bot_username`
4. Monitor growth with `stats.py`
5. Add more job sources (Upwork, Fiverr scraping)
6. Build referral system
7. Expand to other platforms (Discord, Email)

## Cost

- **Hosting**: Free (runs on your machine)
- **APIs**: Free (all sources are free)
- **Revenue**: 70% of Telegram Stars → USD

At 10 users paying $2/month: **$14/month revenue** (covers minimal server costs)

At 100 users: **$140/month revenue** (profit!)

---

**Status**: MVP Ready  
**Build Time**: 3 hours  
**Time to Market**: <1 week  
**Time to 10 Paying Users**: 2-4 weeks  

Questions? Check `DEPLOYMENT.md`
