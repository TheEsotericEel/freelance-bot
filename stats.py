#!/usr/bin/env python3
"""
Stats & management script for Freelance Job Alerts Bot
Run this to check health, user metrics, and debug issues
"""

import sqlite3
import json
from datetime import datetime, timedelta
from config import DB_PATH

def print_header(text):
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60)

def get_user_stats():
    """User metrics"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    print_header("USER STATS")
    
    # Total users
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    print(f"📊 Total Users: {total_users}")
    
    # Premium vs Free
    c.execute("SELECT subscription_level, COUNT(*) FROM users GROUP BY subscription_level")
    for level, count in c.fetchall():
        print(f"   • {level.upper()}: {count} ({count*100//max(1,total_users)}%)")
    
    # New users (last 7 days)
    c.execute("""
        SELECT COUNT(*) FROM users 
        WHERE created_at > datetime('now', '-7 days')
    """)
    new_7d = c.fetchone()[0]
    print(f"   • New (last 7 days): {new_7d}")
    
    # Active users (used /jobs in last 24h)
    c.execute("""
        SELECT COUNT(DISTINCT user_id) FROM user_jobs_sent 
        WHERE sent_at > datetime('now', '-1 day')
    """)
    active_24h = c.fetchone()[0]
    print(f"   • Active (last 24h): {active_24h}")
    
    conn.close()

def get_job_stats():
    """Job metrics"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    print_header("JOB STATS")
    
    # Total jobs
    c.execute("SELECT COUNT(*) FROM jobs")
    total_jobs = c.fetchone()[0]
    print(f"💼 Total Jobs: {total_jobs}")
    
    # By platform
    c.execute("SELECT platform, COUNT(*) FROM jobs GROUP BY platform ORDER BY COUNT(*) DESC")
    for platform, count in c.fetchall():
        print(f"   • {platform}: {count}")
    
    # Fresh jobs (last 24h)
    c.execute("""
        SELECT COUNT(*) FROM jobs 
        WHERE posted_at > datetime('now', '-1 day')
    """)
    fresh_24h = c.fetchone()[0]
    print(f"   • Added (last 24h): {fresh_24h}")
    
    # Average job age
    c.execute("""
        SELECT AVG((julianday('now') - julianday(posted_at)) * 24) as avg_hours
        FROM jobs
    """)
    avg_age = c.fetchone()[0]
    if avg_age:
        print(f"   • Average age: {avg_age:.1f} hours")
    
    conn.close()

def get_revenue_stats():
    """Revenue metrics (projections)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    print_header("REVENUE STATS")
    
    # Premium users
    c.execute("SELECT COUNT(*) FROM users WHERE subscription_level = 'premium'")
    premium_users = c.fetchone()[0]
    
    # Estimate MRR (assuming 30-day subscription)
    STARS_PER_MONTH = 200
    STARS_TO_USD = 1/100  # Rough estimate
    estimated_mrr = premium_users * STARS_PER_MONTH * STARS_TO_USD
    
    print(f"💰 Premium Users: {premium_users}")
    print(f"   • Estimated MRR: ${estimated_mrr:.2f}")
    print(f"   • Monthly subscription: 200⭐ (~$2 USD)")
    
    # Conversion rate
    c.execute("SELECT COUNT(*) FROM users WHERE subscription_level = 'free'")
    free_users = c.fetchone()[0]
    
    total = premium_users + free_users
    if total > 0:
        conversion = (premium_users / total) * 100
        print(f"   • Conversion rate: {conversion:.1f}%")
    
    # Projected revenue at scale
    print(f"\n📈 Projections (assuming current conversion):")
    for scale in [100, 500, 1000]:
        projected_premium = int(scale * (premium_users / max(1, total)))
        projected_mrr = projected_premium * STARS_PER_MONTH * STARS_TO_USD
        print(f"   • At {scale} users: ${projected_mrr:.2f} MRR (~{projected_premium} premium)")
    
    conn.close()

def get_alert_stats():
    """Alert delivery metrics"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    print_header("ALERT STATS")
    
    # Total alerts sent
    c.execute("SELECT COUNT(*) FROM user_jobs_sent")
    total_alerts = c.fetchone()[0]
    print(f"📬 Total alerts sent: {total_alerts}")
    
    # Alerts today
    c.execute("""
        SELECT COUNT(*) FROM user_jobs_sent 
        WHERE sent_at > datetime('now', 'start of day')
    """)
    today_alerts = c.fetchone()[0]
    print(f"   • Today: {today_alerts}")
    
    # Top 5 users (by clicks)
    c.execute("""
        SELECT user_id, COUNT(*) as clicks FROM user_jobs_sent 
        GROUP BY user_id 
        ORDER BY clicks DESC LIMIT 5
    """)
    print(f"\n   🔥 Top users by engagement:")
    for user_id, clicks in c.fetchall():
        print(f"      User {user_id}: {clicks} jobs viewed")
    
    # Check if cron is running (last fetch time)
    c.execute("SELECT MAX(fetched_at) FROM jobs")
    last_fetch = c.fetchone()[0]
    if last_fetch:
        print(f"\n   ⏰ Last job fetch: {last_fetch}")
    else:
        print(f"\n   ⚠️  No jobs fetched yet - cron job may not be running!")
    
    conn.close()

def get_db_health():
    """Database health check"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    print_header("DATABASE HEALTH")
    
    # Check table sizes
    c.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
    db_size = c.fetchone()[0]
    print(f"📁 DB Size: {db_size / 1024 / 1024:.2f} MB")
    
    # Table row counts
    tables = ["users", "jobs", "user_jobs_sent", "payments"]
    for table in tables:
        c.execute(f"SELECT COUNT(*) FROM {table}")
        count = c.fetchone()[0]
        print(f"   • {table}: {count} rows")
    
    # Check for issues
    c.execute("SELECT COUNT(*) FROM jobs WHERE title IS NULL")
    null_titles = c.fetchone()[0]
    if null_titles > 0:
        print(f"\n⚠️  Warning: {null_titles} jobs with NULL titles - corruption possible")
    
    conn.close()

def health_check():
    """Overall health check"""
    import subprocess
    import os
    
    print_header("SYSTEM HEALTH CHECK")
    
    # Is bot running?
    result = subprocess.run(["pgrep", "-f", "bot.py"], capture_output=True)
    if result.stdout:
        print(f"✅ Bot process running")
    else:
        print(f"❌ Bot process NOT running - users can't use /jobs command!")
    
    # Does DB exist?
    if os.path.exists(DB_PATH):
        print(f"✅ Database exists")
    else:
        print(f"❌ Database NOT found - run 'python3 bot.py' to initialize")
    
    # Check cron job (Linux/Mac)
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if "cron_worker.py" in result.stdout:
        print(f"✅ Cron job found")
    else:
        print(f"⚠️  Cron job not found - add with: crontab -e")
    
    # Check logs
    if os.path.exists("cron_worker.log"):
        result = subprocess.run(["tail", "-1", "cron_worker.log"], capture_output=True, text=True)
        print(f"\n📋 Latest cron log:")
        print(f"   {result.stdout.strip()}")

def main():
    """Run all stats"""
    print("\n🤖 FREELANCE JOB ALERTS BOT - STATS & DIAGNOSTICS")
    
    try:
        get_user_stats()
        get_job_stats()
        get_alert_stats()
        get_revenue_stats()
        get_db_health()
        health_check()
        
        print_header("✅ ALL CHECKS COMPLETE")
        
    except FileNotFoundError:
        print(f"\n❌ ERROR: Database not found at {DB_PATH}")
        print(f"   Run: python3 -c \"from bot import init_db; init_db()\"")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
