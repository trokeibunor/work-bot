import asyncio
import logging
import re
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.workers.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models import TargetCompany, Job, JobSource, JobStatus

logger = logging.getLogger("ats_scraper")
logging.basicConfig(level=logging.INFO)

# Pre-filter keywords
EXCLUDE_TITLE_KEYWORDS = [
    "iOS Only", "Staff C++", "Principal Hardware", "US Citizens Only", "Security Clearance Required", "Secret Clearance"
]

ACCEPT_KEYWORDS = [
    "Full Stack", "Frontend", "Backend", "Software Engineer", "Vue", "Nuxt",
    "React", "Python", "FastAPI", "Go", "Golang", "Java", "TypeScript", "Platform", "Endpoint"
]


def check_pre_filter(title: str, description: str) -> bool:
    title_lower = title.lower()
    for ex in EXCLUDE_TITLE_KEYWORDS:
        if ex.lower() in title_lower:
            return False

    content_combined = f"{title} {description}".lower()
    matches = 0
    for kw in ACCEPT_KEYWORDS:
        if re.search(r'\b' + re.escape(kw.lower()) + r'\b', content_combined):
            matches += 1
            if matches >= 2:
                return True

    return matches >= 2


def extract_tech_tags(text: str) -> List[str]:
    tags = []
    text_lower = text.lower()
    tech_map = {
        "vue": "Vue.js", "nuxt": "Nuxt", "react": "React", "typescript": "TypeScript",
        "javascript": "JavaScript", "python": "Python", "fastapi": "FastAPI", "django": "Django",
        "golang": "Go", "go": "Go", "docker": "Docker", "postgres": "PostgreSQL",
        "postgresql": "PostgreSQL", "redis": "Redis", "graphql": "GraphQL", "tailwind": "Tailwind CSS",
        "aws": "AWS", "gcp": "GCP", "linux": "Linux", "rest": "REST API"
    }
    for needle, label in tech_map.items():
        if re.search(r'\b' + re.escape(needle) + r'\b', text_lower):
            if label not in tags:
                tags.append(label)
    return tags


class ATSScraper:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*"
        }

    async def scrape_greenhouse(self, client: httpx.AsyncClient, company: TargetCompany) -> List[Dict[str, Any]]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{company.ats_slug}/jobs?content=true"
        jobs_found = []
        try:
            resp = await client.get(url, headers=self.headers, timeout=20.0)
            if resp.status_code != 200:
                logger.warning(f"Greenhouse [{company.name}] returned status {resp.status_code}")
                return []
            data = resp.json()
            raw_jobs = data.get("jobs", [])
            for rj in raw_jobs:
                title = rj.get("title", "").strip()
                abs_url = rj.get("absolute_url", "").strip()
                external_id = str(rj.get("id", ""))
                loc_obj = rj.get("location", {})
                location = loc_obj.get("name", "") if isinstance(loc_obj, dict) else str(loc_obj)
                
                # Strip HTML tags from content
                raw_html = rj.get("content", "")
                plain_desc = BeautifulSoup(raw_html, "html.parser").get_text(separator="\n").strip()

                if not title or not abs_url or not plain_desc:
                    continue

                if check_pre_filter(title, plain_desc):
                    jobs_found.append({
                        "external_id": external_id,
                        "source": JobSource.GREENHOUSE,
                        "source_url": abs_url,
                        "company_name": company.name,
                        "job_title": title,
                        "location_raw": location or "Remote",
                        "is_remote_or_relocation_friendly": True,
                        "description_raw": plain_desc,
                        "tech_stack_tags": extract_tech_tags(f"{title} {plain_desc}")
                    })
        except Exception as e:
            logger.error(f"Error scraping Greenhouse for {company.name}: {e}")
        return jobs_found

    async def scrape_lever(self, client: httpx.AsyncClient, company: TargetCompany) -> List[Dict[str, Any]]:
        url = f"https://api.lever.co/v0/postings/{company.ats_slug}?mode=json"
        jobs_found = []
        try:
            resp = await client.get(url, headers=self.headers, timeout=20.0)
            if resp.status_code != 200:
                logger.warning(f"Lever [{company.name}] returned status {resp.status_code}")
                return []
            raw_jobs = resp.json()
            if not isinstance(raw_jobs, list):
                return []
            for rj in raw_jobs:
                title = rj.get("text", "").strip()
                hosted_url = rj.get("hostedUrl", "").strip()
                external_id = str(rj.get("id", ""))
                categories = rj.get("categories", {})
                location = categories.get("location", "") if isinstance(categories, dict) else ""
                plain_desc = rj.get("descriptionPlain", "") or BeautifulSoup(rj.get("description", ""), "html.parser").get_text(separator="\n").strip()

                if not title or not hosted_url or not plain_desc:
                    continue

                if check_pre_filter(title, plain_desc):
                    jobs_found.append({
                        "external_id": external_id,
                        "source": JobSource.LEVER,
                        "source_url": hosted_url,
                        "company_name": company.name,
                        "job_title": title,
                        "location_raw": location or "Remote",
                        "is_remote_or_relocation_friendly": True,
                        "description_raw": plain_desc,
                        "tech_stack_tags": extract_tech_tags(f"{title} {plain_desc}")
                    })
        except Exception as e:
            logger.error(f"Error scraping Lever for {company.name}: {e}")
        return jobs_found

    async def scrape_ashby(self, client: httpx.AsyncClient, company: TargetCompany) -> List[Dict[str, Any]]:
        url = "https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams"
        query = """query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) {
            jobBoard: jobBoardWithTeams(organizationHostedJobsPageName: $organizationHostedJobsPageName) {
                jobs {
                    id
                    title
                    location
                    secondaryLocations { location }
                    jobUrl
                    isRemote
                    descriptionPlain
                }
            }
        }"""
        payload = {
            "operationName": "ApiJobBoardWithTeams",
            "variables": {"organizationHostedJobsPageName": company.ats_slug},
            "query": query
        }
        jobs_found = []
        try:
            resp = await client.post(url, json=payload, headers=self.headers, timeout=20.0)
            if resp.status_code != 200:
                logger.warning(f"Ashby [{company.name}] returned status {resp.status_code}")
                return []
            data = resp.json()
            job_board = data.get("data", {}).get("jobBoard", {}) or {}
            raw_jobs = job_board.get("jobs", [])
            for rj in raw_jobs:
                title = rj.get("title", "").strip()
                job_url = rj.get("jobUrl", "").strip()
                external_id = str(rj.get("id", ""))
                location = rj.get("location", "")
                plain_desc = rj.get("descriptionPlain", "").strip()

                if not title or not job_url or not plain_desc:
                    continue

                if check_pre_filter(title, plain_desc):
                    jobs_found.append({
                        "external_id": external_id,
                        "source": JobSource.ASHBY,
                        "source_url": job_url,
                        "company_name": company.name,
                        "job_title": title,
                        "location_raw": location or "Remote",
                        "is_remote_or_relocation_friendly": True,
                        "description_raw": plain_desc,
                        "tech_stack_tags": extract_tech_tags(f"{title} {plain_desc}")
                    })
        except Exception as e:
            logger.error(f"Error scraping Ashby for {company.name}: {e}")
        return jobs_found

    async def scrape_all_targets(self) -> int:
        async with AsyncSessionLocal() as session:
            stmt = select(TargetCompany).where(TargetCompany.is_active.is_(True))
            result = await session.execute(stmt)
            companies = result.scalars().all()

        inserted_count = 0
        from app.workers.llm_tailor import tailor_job_task

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            for company in companies:
                logger.info(f"Scraping {company.ats_provider.value} board for: {company.name}")
                if company.ats_provider == JobSource.GREENHOUSE:
                    found = await self.scrape_greenhouse(client, company)
                elif company.ats_provider == JobSource.LEVER:
                    found = await self.scrape_lever(client, company)
                elif company.ats_provider == JobSource.ASHBY:
                    found = await self.scrape_ashby(client, company)
                else:
                    found = []

                for j in found:
                    async with AsyncSessionLocal() as session:
                        # Check existing by source_url
                        existing = await session.execute(
                            select(Job.id).where(Job.source_url == j["source_url"])
                        )
                        if existing.scalar_one_or_none() is None:
                            new_job = Job(
                                external_id=j["external_id"],
                                source=j["source"],
                                source_url=j["source_url"],
                                company_name=j["company_name"],
                                job_title=j["job_title"],
                                location_raw=j["location_raw"],
                                is_remote_or_relocation_friendly=j["is_remote_or_relocation_friendly"],
                                description_raw=j["description_raw"],
                                tech_stack_tags=j["tech_stack_tags"],
                                status=JobStatus.QUEUED_FOR_LLM
                            )
                            session.add(new_job)
                            await session.commit()
                            await session.refresh(new_job)
                            inserted_count += 1
                            logger.info(f"Queued job for LLM tailoring: {new_job.job_title} at {new_job.company_name}")
                            tailor_job_task.delay(str(new_job.id))

        logger.info(f"Scrape completed. Total new qualified jobs inserted: {inserted_count}")
        return inserted_count


@celery_app.task(name="app.workers.ats_scraper.scrape_all_target_companies_task")
def scrape_all_target_companies_task() -> int:
    scraper = ATSScraper()
    return asyncio.run(scraper.scrape_all_targets())


if __name__ == "__main__":
    scraper = ATSScraper()
    asyncio.run(scraper.scrape_all_targets())
