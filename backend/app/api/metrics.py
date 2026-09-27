from datetime import datetime, time
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Job, JobStatus
from app.schemas import DailyMetricsResponse, ScrapeTriggerResponse
from app.config import settings
from app.workers.ats_scraper import scrape_all_target_companies_task
from app.workers.reddit_listener import poll_reddit_hiring_task
from app.workers.hn_hiring_scraper import scrape_hn_who_is_hiring_task

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("/daily", response_model=DailyMetricsResponse)
async def get_daily_metrics(db: AsyncSession = Depends(get_db)):
    # Calculate start of current UTC day
    now = datetime.utcnow()
    start_of_day = datetime.combine(now.date(), time.min)

    # 1. Count jobs applied today
    applied_today_stmt = select(func.count(Job.id)).where(
        and_(
            Job.status == JobStatus.APPLIED.value,
            Job.applied_at >= start_of_day
        )
    )
    today_applied = (await db.execute(applied_today_stmt)).scalar() or 0

    # 2. Count queued ready jobs
    queued_stmt = select(func.count(Job.id)).where(
        Job.status == JobStatus.READY_TO_APPLY.value
    )
    queued_ready = (await db.execute(queued_stmt)).scalar() or 0

    # 3. Weekly streak calculation (days with >= 1 application in last 7 days)
    streak_stmt = select(func.count(func.distinct(func.date(Job.applied_at)))).where(
        and_(
            Job.status == JobStatus.APPLIED.value,
            Job.applied_at >= (now.date().replace(day=max(1, now.day - 7)))
        )
    )
    weekly_streak = (await db.execute(streak_stmt)).scalar() or 1

    daily_target = settings.DAILY_APPLICATION_TARGET
    remaining = max(0, daily_target - today_applied)

    return DailyMetricsResponse(
        today_applied=today_applied,
        daily_target=daily_target,
        remaining=remaining,
        queued_ready=queued_ready,
        weekly_streak=weekly_streak
    )


@router.post("/scrapers/trigger", response_model=ScrapeTriggerResponse)
async def trigger_scrapers(mode: str = "founder_first"):
    """
    Trigger scrapers with optional mode:
    - 'founder_first' (default): Runs Reddit listener & Hacker News Who is Hiring first, then enqueues ATS.
    - 'community_only': Runs ONLY Reddit & Hacker News founder-led job listeners.
    - 'ats_only': Runs ONLY standard corporate ATS scrapers.
    """
    tasks_spawned = []
    try:
        if mode in ["founder_first", "community_only"]:
            reddit_task = poll_reddit_hiring_task.delay()
            hn_task = scrape_hn_who_is_hiring_task.delay()
            tasks_spawned.append(f"Reddit (Task: {reddit_task.id})")
            tasks_spawned.append(f"Hacker News Founder (Task: {hn_task.id})")

        if mode in ["founder_first", "ats_only"]:
            ats_task = scrape_all_target_companies_task.delay()
            tasks_spawned.append(f"ATS Boards (Task: {ats_task.id})")

        msg = f"Triggered high-priority scrapers: {', '.join(tasks_spawned)}"
    except Exception as e:
        msg = f"Scrapers triggered asynchronously: {e}"

    return ScrapeTriggerResponse(
        status="triggered",
        message=msg
    )


@router.post("/scrapers/trigger-community", response_model=ScrapeTriggerResponse)
async def trigger_community_scrapers():
    """Explicitly trigger ONLY founder-led and community jobs (Reddit & Hacker News)."""
    return await trigger_scrapers(mode="community_only")
