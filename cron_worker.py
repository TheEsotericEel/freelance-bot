#!/usr/bin/env python3
"""
Standalone cron worker - runs periodic jobs without keeping bot online
Fetch jobs and queue alerts for sending
"""

import os
import sqlite3
import json
import requests
import logging
from datetime import datetime, timedelta
import hashlib

DB_PATH = "freelance_bot.db"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cron_worker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============ JOB FETCHERS ============
def fetch_remoteok_jobs():
    """Fetch jobs from RemoteOK"""
    try:
        response = requests.get("https://remoteok.io/api", timeout=10)
        jobs = []
        
        if response.status_code == 200:
            data = response.json()
            for job in data[:20]:
                if job.get("type") != "job":
                    continue
                
                jobs.append({
                    "id": f"remoteok_{job.get('id')}",
                    "title": job.get("position"),
                    "description": job.get("description", "")[:500],
                    "budget_min": None,
                    "budget_max": None,
                    "skills": json.dumps(job.get("tags", [])),
                    "url": job.get("url"),
                    "platform": "RemoteOK",
                    "posted_at": datetime.now().isoformat()
                })
        
        logger.info(f"Fetched {len(jobs)} jobs from RemoteOK")
        return jobs
    except Exception as e:
        logger.error(f"Error fetching RemoteOK jobs: {e}")
        return []

def fetch_hn_jobs():
    """Fetch jobs from Hacker News"""
    try:
        response = requests.get(
            "https://hacker-news.firebaseio.com/v0/jobstories.json",
            timeout=10
        )
        
        jobs = []
        if response.status_code == 200:
            job_ids = response.json()[:10]
            
            for job_id in job_ids:
                try:
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
                            "skills": "[]",
                            "url": job_data.get("url", ""),
                            "platform": "Hacker News",
                            "posted_at": datetime.now().isoformat()
                        })
                except:
                    continue
        
        logger.info(f"Fetched {len(jobs)} jobs from HN")
        return jobs
    except Exception as e:
        logger.error(f"Error fetching HN jobs: {e}")
        return []

def fetch_all_jobs():
    """Fetch from all sources and save to DB"""
    all_jobs = []
    all_jobs.extend(fetch_remoteok_jobs())
    all_jobs.extend(fetch_hn_jobs())
    
    logger.info(f"Fetched {len(all_jobs)} total jobs")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    for job in all_jobs:
        try:
            c.execute('''INSERT OR IGNORE INTO jobs 
                (id, title, description, budget_min, budget_max, skills, url, platform, posted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (job["id"], job["title"], job["description"], 
                 job.get("budget_min"), job.get("budget_max"),
                 job["skills"], job["url"], job["platform"], job["posted_at"]))
        except Exception as e:
            logger.error(f"Error inserting job: {e}")
    
    conn.commit()
    conn.close()
    
    logger.info("Job fetch complete")

def send_alerts_to_premium_users():
    """Queue alerts for all premium users"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get premium users who haven't been alerted in last hour
    one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
    c.execute("""
        SELECT id, telegram_id FROM users 
        WHERE subscription_level = 'premium' 
        AND (last_alert_sent IS NULL OR last_alert_sent < ?)
    """, (one_hour_ago,))
    
    users = c.fetchall()
    logger.info(f"Preparing alerts for {len(users)} users")
    
    alerts_queued = 0
    for user_id, telegram_id in users:
        # Get new jobs for this user (not sent yet)
        c.execute("""
            SELECT id, title, url, platform FROM jobs 
            WHERE id NOT IN (SELECT job_id FROM user_jobs_sent WHERE user_id = ?)
            ORDER BY posted_at DESC LIMIT 5
        """, (user_id,))
        
        new_jobs = c.fetchall()
        
        if new_jobs:
            # Create alert record (for future webhook/API integration)
            for job_id, title, url, platform in new_jobs:
                c.execute("""
                    INSERT OR IGNORE INTO user_jobs_sent (user_id, job_id) 
                    VALUES (?, ?)
                """, (user_id, job_id))
            
            # Update last alert sent
            c.execute(
                "UPDATE users SET last_alert_sent = ? WHERE id = ?",
                (datetime.now().isoformat(), user_id)
            )
            
            alerts_queued += len(new_jobs)
            logger.info(f"Queued {len(new_jobs)} jobs for user {telegram_id}")
    
    conn.commit()
    conn.close()
    
    logger.info(f"Total alerts queued: {alerts_queued}")

def cleanup_old_jobs():
    """Remove jobs older than 30 days"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
    c.execute("DELETE FROM jobs WHERE posted_at < ?", (thirty_days_ago,))
    
    deleted = c.rowcount
    conn.commit()
    conn.close()
    
    logger.info(f"Cleaned up {deleted} old jobs")

def main():
    """Main cron job"""
    logger.info("=" * 50)
    logger.info("Cron worker started")
    
    # Fetch fresh jobs
    fetch_all_jobs()
    
    # Send alerts to premium users
    send_alerts_to_premium_users()
    
    # Cleanup old jobs
    cleanup_old_jobs()
    
    logger.info("Cron worker completed")
    logger.info("=" * 50)

if __name__ == "__main__":
    main()
