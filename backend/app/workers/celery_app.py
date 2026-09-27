import asyncio
from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "jate_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.reddit_listener",
        "app.workers.hn_hiring_scraper",
        "app.workers.ats_scraper",
        "app.workers.llm_tailor"
    ]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,
    worker_prefetch_multiplier=1,
)

# Celery Beat Periodic Schedule - Prioritize Founder & Community Opportunities First
celery_app.conf.beat_schedule = {
    # 1. Run Reddit listener every 20 minutes
    "poll-reddit-hiring-every-20-minutes": {
        "task": "app.workers.reddit_listener.poll_reddit_hiring_task",
        "schedule": 1200.0,
    },
    # 2. Run Hacker News Who is Hiring scraper every hour
    "scrape-hn-who-is-hiring-hourly": {
        "task": "app.workers.hn_hiring_scraper.scrape_hn_who_is_hiring_task",
        "schedule": 3600.0,
    },
    # 3. Run ATS job board scrapers every 6 hours
    "scrape-ats-every-6-hours": {
        "task": "app.workers.ats_scraper.scrape_all_target_companies_task",
        "schedule": 21600.0,
    }
}
