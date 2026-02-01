#!/usr/bin/env python3
"""
Freelance Job Alerts Bot for Telegram
Aggregates jobs from multiple sources, sends curated alerts based on user preferences
"""

import os
import json
import sqlite3
import logging
from datetime import datetime, timedelta
import hashlib
import requests
from typing import List, Dict, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError
import asyncio

# ============ CONFIG ============
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set. Please set it before running the bot.")
DB_PATH = "freelance_bot.db"
JOBS_FETCH_INTERVAL = 3600  # 1 hour in seconds

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ DATABASE ============
def init_db():
    """Initialize SQLite database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        filters_json TEXT,
        subscription_level TEXT DEFAULT 'free',
        credits_remaining INTEGER DEFAULT 5,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_alert_sent TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        title TEXT,
        description TEXT,
        budget_min INTEGER,
        budget_max INTEGER,
        skills TEXT,
        url TEXT,
        platform TEXT,
        posted_at TIMESTAMP,
        fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS user_jobs_sent (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        job_id TEXT,
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, job_id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount_stars INTEGER,
        subscription_days INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    conn.commit()
    conn.close()

def get_user(telegram_id: int) -> Optional[Dict]:
    """Fetch user from DB"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        return None
    
    return {
        "id": row[0],
        "telegram_id": row[1],
        "filters": json.loads(row[2]) if row[2] else {},
        "subscription_level": row[3],
        "credits_remaining": row[4],
        "created_at": row[5],
        "last_alert_sent": row[6]
    }

def create_or_update_user(telegram_id: int, filters: Dict = None, subscription_level: str = "free"):
    """Create/update user"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    user = get_user(telegram_id)
    filters_json = json.dumps(filters or {})
    
    if user:
        c.execute(
            "UPDATE users SET filters_json = ?, subscription_level = ? WHERE telegram_id = ?",
            (filters_json, subscription_level, telegram_id)
        )
    else:
        c.execute(
            "INSERT INTO users (telegram_id, filters_json, subscription_level) VALUES (?, ?, ?)",
            (telegram_id, filters_json, subscription_level)
        )
    
    conn.commit()
    conn.close()

def save_jobs(jobs: List[Dict]):
    """Save fetched jobs to DB"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    for job in jobs:
        job_id = job.get("id", hashlib.md5(job.get("title", "").encode()).hexdigest())
        
        try:
            c.execute('''INSERT OR IGNORE INTO jobs 
                (id, title, description, budget_min, budget_max, skills, url, platform, posted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (job_id, job.get("title"), job.get("description"), 
                 job.get("budget_min"), job.get("budget_max"),
                 json.dumps(job.get("skills", [])), job.get("url"),
                 job.get("platform"), job.get("posted_at")))
        except Exception as e:
            logger.error(f"Error saving job {job_id}: {e}")
    
    conn.commit()
    conn.close()

def get_unsent_jobs(user_id: int, telegram_id: int) -> List[Dict]:
    """Get jobs matching user filters that haven't been sent yet"""
    user = get_user(telegram_id)
    if not user:
        return []
    
    filters = user.get("filters", {})
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Build query based on filters
    query = "SELECT * FROM jobs WHERE id NOT IN (SELECT job_id FROM user_jobs_sent WHERE user_id = ?)"
    params = [user_id]
    
    if filters.get("min_budget"):
        query += " AND (budget_max IS NULL OR budget_max >= ?)"
        params.append(filters["min_budget"])
    
    if filters.get("max_budget"):
        query += " AND (budget_min IS NULL OR budget_min <= ?)"
        params.append(filters["max_budget"])
    
    if filters.get("skills"):
        # TODO: Implement skill matching (for MVP, skip)
        pass
    
    query += " ORDER BY posted_at DESC LIMIT 10"
    
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        results.append({
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "budget_min": row[3],
            "budget_max": row[4],
            "skills": json.loads(row[5]) if row[5] else [],
            "url": row[6],
            "platform": row[7]
        })
    
    return results

def mark_jobs_sent(user_id: int, job_ids: List[str]):
    """Mark jobs as sent to user"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    for job_id in job_ids:
        try:
            c.execute("INSERT OR IGNORE INTO user_jobs_sent (user_id, job_id) VALUES (?, ?)",
                     (user_id, job_id))
        except:
            pass
    
    conn.commit()
    conn.close()

# ============ JOB FETCHERS ============
def fetch_remoteok_jobs() -> List[Dict]:
    """Fetch jobs from RemoteOK (free API)"""
    try:
        response = requests.get("https://remoteok.io/api", timeout=10)
        jobs = []
        
        if response.status_code == 200:
            data = response.json()
            for job in data[:20]:  # Limit to 20 to avoid spam
                # Skip non-job entries
                if job.get("type") != "job":
                    continue
                
                jobs.append({
                    "id": f"remoteok_{job.get('id')}",
                    "title": job.get("position"),
                    "description": job.get("description", "")[:500],
                    "budget_min": None,
                    "budget_max": None,
                    "skills": job.get("tags", []),
                    "url": job.get("url"),
                    "platform": "RemoteOK",
                    "posted_at": datetime.now().isoformat()
                })
        
        return jobs
    except Exception as e:
        logger.error(f"Error fetching RemoteOK jobs: {e}")
        return []

def fetch_hn_jobs() -> List[Dict]:
    """Fetch jobs from Hacker News Jobs API"""
    try:
        # HN API for job stories
        response = requests.get(
            "https://hacker-news.firebaseio.com/v0/jobstories.json",
            timeout=10
        )
        
        jobs = []
        if response.status_code == 200:
            job_ids = response.json()[:10]  # Get first 10
            
            for job_id in job_ids:
                job_response = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{job_id}.json",
                    timeout=5
                )
                
                if job_response.status_code == 200:
                    job_data = job_response.json()
                    
                    jobs.append({
                        "id": f"hn_{job_data.get('id')}",
                        "title": job_data.get("title"),
                        "description": job_data.get("text", "")[:500],
                        "budget_min": None,
                        "budget_max": None,
                        "skills": [],
                        "url": job_data.get("url", ""),
                        "platform": "Hacker News",
                        "posted_at": datetime.now().isoformat()
                    })
        
        return jobs
    except Exception as e:
        logger.error(f"Error fetching HN jobs: {e}")
        return []

def fetch_github_jobs() -> List[Dict]:
    """Fetch jobs from GitHub Jobs API (deprecated but still works)"""
    try:
        response = requests.get(
            "https://api.github.com/repos/github/jobs/issues?labels=job&per_page=20",
            timeout=10
        )
        
        jobs = []
        if response.status_code == 200:
            issues = response.json()
            
            for issue in issues[:10]:
                jobs.append({
                    "id": f"gh_{issue.get('id')}",
                    "title": issue.get("title"),
                    "description": issue.get("body", "")[:500],
                    "budget_min": None,
                    "budget_max": None,
                    "skills": [],
                    "url": issue.get("html_url"),
                    "platform": "GitHub",
                    "posted_at": issue.get("created_at")
                })
        
        return jobs
    except Exception as e:
        logger.error(f"Error fetching GitHub jobs: {e}")
        return []

def fetch_all_jobs() -> List[Dict]:
    """Fetch from all sources"""
    all_jobs = []
    all_jobs.extend(fetch_remoteok_jobs())
    all_jobs.extend(fetch_hn_jobs())
    all_jobs.extend(fetch_github_jobs())
    
    logger.info(f"Fetched {len(all_jobs)} total jobs")
    save_jobs(all_jobs)
    
    return all_jobs

# ============ TELEGRAM HANDLERS ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    telegram_id = update.effective_user.id
    create_or_update_user(telegram_id)
    
    message = (
        "🚀 **Welcome to Freelance Job Alerts!**\n\n"
        "Get notified about new jobs matching your skills and budget.\n\n"
        "Commands:\n"
        "• /filter - Set your job preferences\n"
        "• /jobs - Get current job matches\n"
        "• /upgrade - Go premium (unlimited alerts)\n"
        "• /help - Show help\n\n"
        "_Free tier: 5 jobs/day_\n"
        "_Premium: Unlimited + hourly alerts_"
    )
    
    await update.message.reply_text(message, parse_mode="Markdown")

async def show_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show filter setup"""
    telegram_id = update.effective_user.id
    
    keyboard = [
        [InlineKeyboardButton("💰 Budget Range", callback_data="filter_budget")],
        [InlineKeyboardButton("🛠️ Skills", callback_data="filter_skills")],
        [InlineKeyboardButton("📍 Job Type", callback_data="filter_type")],
        [InlineKeyboardButton("✅ Done", callback_data="filter_done")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Configure your preferences:", reply_markup=reply_markup)

async def show_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send user their matching jobs"""
    telegram_id = update.effective_user.id
    user = get_user(telegram_id)
    
    if not user:
        await update.message.reply_text("Please /start first")
        return
    
    jobs = get_unsent_jobs(user["id"], telegram_id)
    
    if not jobs:
        await update.message.reply_text("No matching jobs found. Try adjusting your filters with /filter")
        return
    
    # Respect free tier limit
    if user["subscription_level"] == "free":
        jobs = jobs[:5]
        remaining = user["credits_remaining"] - len(jobs)
        if remaining < 0:
            jobs = jobs[:user["credits_remaining"]]
    
    job_ids_sent = []
    for job in jobs:
        job_text = (
            f"**{job['title']}**\n"
            f"Platform: {job['platform']}\n"
            f"Budget: ${job['budget_min']}-${job['budget_max']}\n\n"
            f"{job['description'][:200]}...\n\n"
            f"[View Job]({job['url']})"
        )
        
        try:
            await update.message.reply_text(job_text, parse_mode="Markdown")
            job_ids_sent.append(job["id"])
        except TelegramError as e:
            logger.error(f"Error sending job: {e}")
    
    # Mark as sent
    if job_ids_sent:
        mark_jobs_sent(user["id"], job_ids_sent)
    
    if user["subscription_level"] == "free":
        await update.message.reply_text(
            f"📊 You have {remaining} jobs left today (free tier)\n"
            "Upgrade to premium for unlimited access: /upgrade"
        )

async def upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show upgrade options"""
    keyboard = [
        [InlineKeyboardButton("1 Month - 200 ⭐", callback_data="upgrade_month")],
        [InlineKeyboardButton("3 Months - 500 ⭐", callback_data="upgrade_3m")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "💎 **Premium Features**\n"
        "• Unlimited job alerts\n"
        "• Hourly notifications\n"
        "• Advanced filtering\n"
        "• Skill matching\n\n"
        "Choose a plan:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button presses"""
    query = update.callback_query
    telegram_id = query.from_user.id
    
    if query.data.startswith("upgrade_"):
        plan = query.data.split("_")[1]
        
        if plan == "month":
            stars = 200
            days = 30
        else:
            stars = 500
            days = 90
        
        # In production, use Telegram's payment API
        # For MVP, just mark as premium
        create_or_update_user(telegram_id, subscription_level="premium")
        
        await query.answer("✅ You're now premium!")
        await query.edit_message_text(f"Great! You have premium access for {days} days.\n/jobs to start!")
    
    await query.answer()

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help"""
    help_text = (
        "📖 **Help**\n\n"
        "/start - Initialize bot\n"
        "/jobs - Show matching jobs\n"
        "/filter - Set preferences\n"
        "/upgrade - Go premium\n"
        "/help - This message\n\n"
        "**Free vs Premium:**\n"
        "Free: 5 jobs/day, manual checks\n"
        "Premium: Unlimited, hourly alerts\n\n"
        "Questions? Support coming soon!"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

# ============ CRON JOBS ============
async def fetch_jobs_job(context: ContextTypes.DEFAULT_TYPE):
    """Periodic job fetcher"""
    logger.info("Fetching jobs...")
    fetch_all_jobs()

async def send_alerts_job(context: ContextTypes.DEFAULT_TYPE):
    """Send alerts to premium users"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, telegram_id FROM users WHERE subscription_level = 'premium'")
    users = c.fetchall()
    conn.close()
    
    logger.info(f"Sending alerts to {len(users)} premium users")
    
    for user_id, telegram_id in users:
        try:
            jobs = get_unsent_jobs(user_id, telegram_id)
            if jobs:
                # Send first 5 jobs
                for job in jobs[:5]:
                    job_text = f"*{job['title']}* ({job['platform']})\n[View]({job['url']})"
                    await context.bot.send_message(telegram_id, job_text, parse_mode="Markdown")
                
                # Mark as sent
                job_ids = [j["id"] for j in jobs[:5]]
                mark_jobs_sent(user_id, job_ids)
        except Exception as e:
            logger.error(f"Error sending alert to {telegram_id}: {e}")

async def post_init(application: Application):
    """Setup after bot initialization"""
    job_queue = application.job_queue
    
    # Fetch jobs every hour
    job_queue.run_repeating(fetch_jobs_job, interval=3600, first=0)
    
    # Send alerts every hour to premium users
    job_queue.run_repeating(send_alerts_job, interval=3600, first=300)

# ============ MAIN ============
def main():
    """Start the bot"""
    init_db()
    
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("filter", show_filters))
    application.add_handler(CommandHandler("jobs", show_jobs))
    application.add_handler(CommandHandler("upgrade", upgrade))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    logger.info("Bot starting...")
    application.run_polling()

if __name__ == "__main__":
    main()
