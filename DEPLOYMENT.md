# Freelance Job Alerts Bot - Deployment & Management Guide

## Overview
Freelance Job Alerts Bot aggregates jobs from multiple sources (RemoteOK, Hacker News, GitHub) and sends curated alerts to Telegram users.

- **Free tier**: 5 jobs/day, manual `/jobs` command
- **Premium**: Unlimited jobs + hourly automated alerts (200 Telegram Stars/month)

## Architecture

### Components
1. **bot.py** - Main Telegram bot (long-running, handles user commands)
2. **cron_worker.py** - Standalone job fetcher & alert queuer (runs hourly)
3. **SQLite DB** - Stores users, jobs, and user preferences

### Data Flow
```
cron_worker.py (hourly)
  ↓
Fetch jobs from APIs → Store in DB
  ↓
Queue alerts for premium users
  ↓
bot.py listens for commands + sends queued alerts
```

## Setup Instructions

### 1. Prerequisites
- Python 3.8+
- pip/virtualenv
- Telegram account + @BotFather access

### 2. Create Telegram Bot
```bash
# Go to Telegram and message @BotFather
/newbot
# Follow prompts, get your BOT_TOKEN
```

### 3. Install & Configure
```bash
# Clone/navigate to project
cd freelance-bot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set bot token
export TELEGRAM_BOT_TOKEN="your_token_here"

# Initialize database
python3 -c "from bot import init_db; init_db()"
```

### 4. Start the Bot
```bash
python3 bot.py
```

You should see:
```
INFO:telegram.ext._application:Application started
Bot starting...
```

Test in Telegram:
```
/start → Welcome message
/jobs → Get available jobs
/filter → Setup preferences
/upgrade → Premium options
```

### 5. Setup Cron Job for Hourly Fetches (IMPORTANT!)

The bot runs in the foreground listening for commands. Separately, you need to schedule the job fetcher to run periodically.

#### On Linux/Mac:
```bash
# Edit crontab
crontab -e

# Add this line to run every hour:
0 * * * * cd /home/joe/freelance-bot && TELEGRAM_BOT_TOKEN="your_token" /home/joe/freelance-bot/venv/bin/python3 cron_worker.py >> /home/joe/freelance-bot/cron.log 2>&1

# Run every 30 min instead:
*/30 * * * * cd /home/joe/freelance-bot && TELEGRAM_BOT_TOKEN="your_token" /home/joe/freelance-bot/venv/bin/python3 cron_worker.py >> /home/joe/freelance-bot/cron.log 2>&1
```

#### On Windows (using Task Scheduler):
```powershell
# Create task to run every hour
$action = New-ScheduledTaskAction -Execute "C:\path\to\venv\Scripts\python.exe" `
  -Argument "C:\Users\Joe\clawd\freelance-bot\cron_worker.py" `
  -WorkingDirectory "C:\Users\Joe\clawd\freelance-bot"

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 1)

$env:TELEGRAM_BOT_TOKEN = "your_token_here"

Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "FreelanceBotWorker" `
  -Description "Fetch jobs and send alerts"
```

Or simpler - use Windows Task Scheduler GUI:
1. Task Scheduler → Create Basic Task
2. Name: "FreelanceBotWorker"
3. Trigger: "Daily" (or Hourly)
4. Action: Run program `C:\path\to\venv\Scripts\python.exe`
5. Arguments: `C:\Users\Joe\clawd\freelance-bot\cron_worker.py`
6. Set environment: `TELEGRAM_BOT_TOKEN=your_token`

### 6. Running in Background (Production)

#### Using `screen` or `tmux`:
```bash
# Start in detachable session
screen -S freelance-bot python3 bot.py

# Detach: Ctrl+A then D
# Reattach: screen -r freelance-bot
```

#### Using `systemd` (Linux):
Create `/etc/systemd/system/freelance-bot.service`:
```ini
[Unit]
Description=Freelance Job Alerts Bot
After=network.target

[Service]
Type=simple
User=joe
WorkingDirectory=/home/joe/freelance-bot
Environment="TELEGRAM_BOT_TOKEN=your_token_here"
ExecStart=/home/joe/freelance-bot/venv/bin/python3 bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable freelance-bot
sudo systemctl start freelance-bot
sudo systemctl status freelance-bot
```

#### Using PM2 (Node-style, works on any OS):
```bash
npm install -g pm2
pm2 start bot.py --interpreter=python3 --name freelance-bot
pm2 save
pm2 startup
```

## Management

### Check Bot Status
```bash
# Is the bot running?
ps aux | grep bot.py

# Check logs
tail -f cron.log  # Cron job logs
tail -f /var/log/syslog | grep freelance-bot  # Systemd logs
```

### Monitor DB
```bash
# Check users
sqlite3 freelance_bot.db "SELECT COUNT(*) FROM users;"

# Check recent jobs
sqlite3 freelance_bot.db "SELECT title, platform FROM jobs LIMIT 5;"

# Check alert history
sqlite3 freelance_bot.db "SELECT COUNT(*) FROM user_jobs_sent;"
```

### Clear User Data (GDPR)
```bash
sqlite3 freelance_bot.db "DELETE FROM users WHERE telegram_id = 123456789;"
sqlite3 freelance_bot.db "DELETE FROM user_jobs_sent WHERE user_id = 1;"
```

## Troubleshooting

### Bot not responding to commands
- Check if bot is running: `ps aux | grep bot.py`
- Verify bot token is correct
- Restart bot: Kill process and run `python3 bot.py` again

### Jobs not being fetched
- Check cron logs: `tail cron.log`
- Verify cron job is scheduled: `crontab -l`
- Test manually: `python3 cron_worker.py`
- Check API status (RemoteOK, HN might be down)

### Telegram API errors
- Ensure bot token is valid (test with: `curl https://api.telegram.org/bot{TOKEN}/getMe`)
- Rate limits: Telegram limits ~30 messages/second per user

### Database locked
- Kill any other processes using DB: `lsof freelance_bot.db`
- Close any sqlite3 CLI sessions

## API Keys & Free Limits

| Source | API | Limit | Notes |
|--------|-----|-------|-------|
| RemoteOK | Free public API | ~100 jobs/day | No auth needed |
| Hacker News | Firebase REST API | No limit | Free, fast |
| GitHub | Public API | 60 req/hr | Sufficient for job fetches |

All are free and require no API key!

## Monetization

### Current Implementation
- **Free**: 5 jobs/day (manual `/jobs` command)
- **Premium**: Unlimited jobs + hourly alerts via Telegram Stars

### Telegram Stars Payment
Premium users click `/upgrade` → Choose plan (200⭐ = ~$1.99):
- Bot calls Telegram's `sendInvoice()` API
- User pays via Telegram wallet
- You receive Telegram Stars (convertible to $)

### To Enable Payments:
1. Set up bot with @BotFather (bot created already ✓)
2. Add payment provider (Stripe, ClickUp, direct Stars)
3. Implement in bot (currently commented in code, needs integration)

For MVP: Just track subscription_level in DB manually, upgrade via `/upgrade` command.

## Scaling to 100+ Users

### Phase 1: Current (~50 users)
- Single bot process
- Hourly cron job
- SQLite DB (fine for <100K rows)

### Phase 2: 100-1000 users
- Add frequency limiting (premium users can get alerts 2x/day instead of hourly)
- Upgrade to PostgreSQL if DB grows >10GB
- Add Redis queue for alert delivery
- Split bot handlers across multiple processes (webhook mode instead of polling)

### Phase 3: 1000+ users
- Use Telegram webhook instead of polling
- Move to cloud (AWS Lambda + RDS for cron jobs)
- Add user analytics (which jobs are clicked, conversion)
- A/B test premium pricing (freemium to paid conversion optimization)

## Next Steps

1. **Test bot thoroughly** with /start, /jobs, /filter commands
2. **Verify cron job** is running (check logs every hour)
3. **Monitor premium signups** - adjust pricing if too cheap/expensive
4. **Add custom job sources** (Upwork, Fiverr scraping) to stand out
5. **Build referral system** (users get 1 month free if they refer a friend)
6. **Track metrics** (daily active users, premium conversion rate, cost per user)

## Support & Debugging

Enable debug logging:
```python
# In bot.py, change:
logging.basicConfig(level=logging.DEBUG)
```

Or export stats:
```bash
sqlite3 freelance_bot.db "
SELECT 
  'Total Users' as metric, COUNT(*) as value FROM users
UNION ALL
SELECT 'Premium Users', COUNT(*) FROM users WHERE subscription_level='premium'
UNION ALL
SELECT 'Total Jobs Fetched', COUNT(*) FROM jobs
UNION ALL
SELECT 'Alerts Sent', COUNT(*) FROM user_jobs_sent;
"
```

---

**Last Updated**: 2024
**Maintainer**: You (autonomous, cron-based)
**Status**: MVP Ready
