import asyncio
import logging
import re
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select

from app.workers.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models import Job, JobSource, JobStatus
from app.workers.ats_scraper import extract_tech_tags, check_pre_filter

logger = logging.getLogger("hn_hiring_scraper")
logging.basicConfig(level=logging.INFO)

EMAIL_REGEX = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
URL_REGEX = re.compile(r'https?://[^\s\)\]\>\"\'\,]+')

FOUNDER_KEYWORDS = [
    "founder", "co-founder", "cofounder", "our startup", "founding engineer",
    "first engineer", "early engineer", "seed", "pre-seed", "series a", "backed by",
    "dm me", "email me directly", "i'm the founder", "i am the founder", "stealth"
]


class HackerNewsHiringScraper:
    def __init__(self):
        self.firebase_base = "https://hacker-news.firebaseio.com/v0"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        }

    async def get_latest_who_is_hiring_stories(self, client: httpx.AsyncClient, max_threads: int = 2) -> List[int]:
        """Fetch the latest 'Ask HN: Who is hiring?' story IDs."""
        try:
            url = f"{self.firebase_base}/user/whoishiring/submitted.json"
            resp = await client.get(url, timeout=15.0)
            if resp.status_code != 200:
                logger.error(f"Failed to fetch whoishiring submissions: {resp.status_code}")
                return []
            submission_ids = resp.json() or []
            story_ids = []
            for sid in submission_ids[:15]:
                item_url = f"{self.firebase_base}/item/{sid}.json"
                ir = await client.get(item_url, timeout=10.0)
                if ir.status_code == 200:
                    item_data = ir.json() or {}
                    title = item_data.get("title", "")
                    if "Ask HN: Who is hiring?" in title and item_data.get("type") == "story":
                        story_ids.append(sid)
                        logger.info(f"Discovered HN Hiring Thread: '{title}' (ID: {sid})")
                        if len(story_ids) >= max_threads:
                            break
            return story_ids
        except Exception as e:
            logger.error(f"Error fetching HN story IDs: {e}")
            return []

    async def scrape_comments_for_story(self, client: httpx.AsyncClient, story_id: int, max_comments: int = 150) -> List[Dict[str, Any]]:
        """Scrape comments from an 'Ask HN: Who is hiring?' thread."""
        jobs_found = []
        try:
            url = f"{self.firebase_base}/item/{story_id}.json"
            resp = await client.get(url, timeout=15.0)
            if resp.status_code != 200:
                return []
            story_data = resp.json() or {}
            comment_ids = story_data.get("kids", [])[:max_comments]
            logger.info(f"Found {len(comment_ids)} comments in story {story_id}. Processing top-level job postings...")

            for cid in comment_ids:
                try:
                    c_url = f"{self.firebase_base}/item/{cid}.json"
                    cr = await client.get(c_url, timeout=10.0)
                    if cr.status_code != 200:
                        continue
                    cdata = cr.json() or {}
                    if cdata.get("deleted") or cdata.get("dead"):
                        continue

                    raw_html = cdata.get("text", "")
                    if not raw_html:
                        continue

                    clean_text = BeautifulSoup(raw_html, "html.parser").get_text(separator="\n").strip()
                    lines = [line.strip() for line in clean_text.split("\n") if line.strip()]
                    if not lines:
                        continue

                    first_line = lines[0]
                    # Parse header like: Company | Role | Location | Remote/Onsite | Stack
                    parts = [p.strip() for p in first_line.split("|")]
                    company = parts[0] if len(parts) > 0 and len(parts[0]) < 80 else f"Startup (u/{cdata.get('by', 'founder')})"
                    # Clean company name
                    company = re.sub(r'https?://\S+', '', company).strip(' -:()[]') or f"HN Startup (u/{cdata.get('by', 'founder')})"

                    role = parts[1] if len(parts) > 1 and len(parts[1]) < 120 else "Software Engineer"
                    location = parts[2] if len(parts) > 2 else "Remote"
                    is_remote = "remote" in clean_text.lower() or "remote" in location.lower() or "anywhere" in clean_text.lower()

                    # Pre-filter tech stack
                    if not check_pre_filter(f"{role} {company}", clean_text):
                        # Also check if it explicitly mentions founder/startup with core languages
                        lower_text = clean_text.lower()
                        has_core_lang = any(k in lower_text for k in ["python", "golang", "go", "vue", "nuxt", "react", "typescript", "backend", "fullstack", "platform"])
                        if not has_core_lang:
                            continue

                    tech_tags = extract_tech_tags(clean_text)
                    is_founder = any(fk in clean_text.lower() for fk in FOUNDER_KEYWORDS) or True  # All HN who-is-hiring is direct team/founder led

                    external_urls = URL_REGEX.findall(clean_text)
                    clean_urls = [u for u in external_urls if "ycombinator.com" not in u and "news.ycombinator" not in u]
                    hn_permalink = f"https://news.ycombinator.com/item?id={cid}"
                    source_url = clean_urls[0] if clean_urls else hn_permalink

                    jobs_found.append({
                        "external_id": f"hn_{cid}",
                        "source": JobSource.HACKERNEWS,
                        "source_url": hn_permalink,  # Permalink to HN comment for direct outreach context
                        "company_name": company[:200],
                        "job_title": role[:250],
                        "location_raw": location[:200] if location else "Remote",
                        "is_remote_or_relocation_friendly": is_remote,
                        "description_raw": clean_text,
                        "tech_stack_tags": ["Founder-Led", "HN Who is Hiring"] + [t for t in tech_tags if t not in ["Founder-Led", "HN Who is Hiring"]],
                        "is_founder_led": is_founder
                    })
                except Exception as ex:
                    logger.debug(f"Skipping comment {cid}: {ex}")
                    continue

        except Exception as e:
            logger.error(f"Error scraping story {story_id}: {e}")
        return jobs_found

    async def scrape_all_who_is_hiring(self, max_threads: int = 2) -> int:
        """Main entry point to fetch and insert HN founder-led job postings."""
        from app.workers.llm_tailor import tailor_job_task

        inserted_count = 0
        async with httpx.AsyncClient(headers=self.headers, timeout=30.0, follow_redirects=True) as client:
            story_ids = await self.get_latest_who_is_hiring_stories(client, max_threads=max_threads)
            if not story_ids:
                logger.warning("No recent 'Ask HN: Who is hiring?' stories found.")
                return 0

            for sid in story_ids:
                found_jobs = await self.scrape_comments_for_story(client, sid)
                for j in found_jobs:
                    async with AsyncSessionLocal() as session:
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
                                is_founder_led=j["is_founder_led"],
                                status=JobStatus.QUEUED_FOR_LLM
                            )
                            session.add(new_job)
                            await session.commit()
                            await session.refresh(new_job)
                            inserted_count += 1
                            logger.info(f"Queued HN Founder job: {new_job.job_title} at {new_job.company_name} ({new_job.id})")
                            tailor_job_task.delay(str(new_job.id))

                await asyncio.sleep(1.0)

        logger.info(f"Hacker News scraper completed. Total qualified founder-led jobs inserted: {inserted_count}")
        return inserted_count


@celery_app.task(name="app.workers.hn_hiring_scraper.scrape_hn_who_is_hiring_task")
def scrape_hn_who_is_hiring_task(max_threads: int = 2) -> int:
    scraper = HackerNewsHiringScraper()
    return asyncio.run(scraper.scrape_all_who_is_hiring(max_threads=max_threads))


if __name__ == "__main__":
    scraper = HackerNewsHiringScraper()
    asyncio.run(scraper.scrape_all_who_is_hiring())
