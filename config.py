"""
Configuration for Freelance Job Alerts Bot
"""

import os

# ============ TELEGRAM ============
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
if not BOT_TOKEN:
    print("⚠️  WARNING: TELEGRAM_BOT_TOKEN not set. Bot won't work!")
    print("   Set it: export TELEGRAM_BOT_TOKEN='your_token'")

# ============ DATABASE ============
DB_PATH = os.getenv("DB_PATH", "freelance_bot.db")
DB_LOG_PATH = "cron_worker.log"

# ============ MONETIZATION ============
FREE_TIER_JOBS_PER_DAY = 5
PREMIUM_PRICE_STARS = 200  # Telegram Stars (roughly $2 USD)
PREMIUM_PRICE_DURATION_DAYS = 30

# ============ JOB FETCHING ============
FETCH_INTERVAL_SECONDS = 3600  # 1 hour
ALERT_INTERVAL_SECONDS = 3600  # 1 hour
JOBS_PER_FETCH = {
    "remoteok": 20,
    "hackernews": 10,
    "github": 10
}

# ============ CLEANUP ============
DELETE_JOBS_OLDER_THAN_DAYS = 30
DELETE_ALERT_HISTORY_OLDER_THAN_DAYS = 90

# ============ API LIMITS ============
REQUESTS_TIMEOUT = 10  # seconds
MAX_RETRIES = 3

# ============ FEATURES ============
ENABLE_SKILL_FILTERING = False  # TODO: Implement
ENABLE_BUDGET_FILTERING = False  # TODO: Implement in phase 2
ENABLE_WEBHOOKS = False  # TODO: Implement for scale
