import asyncio
import logging
import re
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup
import warnings
from bs4 import XMLParsedAsHTMLWarning
from sqlalchemy import select

from app.config import settings
from app.workers.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models import Job, JobSource, JobStatus
from app.workers.ats_scraper import extract_tech_tags, check_pre_filter

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
logger = logging.getLogger("reddit_listener")
logging.basicConfig(level=logging.INFO)

TARGET_SUBREDDITS = [
    "forhire", "startups", "Jobbit", "hiring", "remotejobs",
    "golang", "pythonjobs", "techjobs", "vuejs", "reactjs"
]

URL_REGEX = re.compile(r'https?://[^\s\)\]\>\"\'\,]+')
EMAIL_REGEX = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')

FOUNDER_KEYWORDS = [
    "founder", "co-founder", "cofounder", "our startup", "my startup",
    "founding engineer", "first engineer", "early engineer", "seed",
    "pre-seed", "series a", "backed by", "dm me", "pm me", "dm's open",
    "reach out directly", "i'm the founder", "i am the founder", "stealth"
]


class RedditListener:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _extract_company_name(self, title: str, author: str, is_founder: bool, subreddit: str) -> str:
        """Extract a readable company name from Reddit post titles."""
        clean_title = re.sub(r'\[hiring\]', '', title, flags=re.IGNORECASE).strip(' -:()[]')

        # Pattern: "Acme is hiring..." or "Acme: Senior Engineer"
        match = re.match(r'^([A-Z][A-Za-z0-9\s\.\,\&]{2,30})\s+(?:is looking for|is hiring|seeking|\:)\s+', clean_title)
        if match:
            extracted = match.group(1).strip()
            if extracted.lower() not in ["remote", "full-time", "part-time", "usa", "worldwide"]:
                return extracted

        # Fallback to author or founder handle
        if is_founder:
            return f"Startup (u/{author})" if author else "Founder-Led Startup"
        return f"r/{subreddit} (u/{author})" if author else f"Reddit r/{subreddit}"

    async def fetch_subreddit_rss(self, client: httpx.AsyncClient, subreddit: str) -> List[Dict[str, Any]]:
        url = f"https://www.reddit.com/r/{subreddit}/.rss"
        posts = []
        try:
            resp = await client.get(url, headers=self.headers, follow_redirects=True, timeout=20.0)
            if resp.status_code == 429:
                logger.warning(f"Reddit r/{subreddit} rate limited (429). Backing off.")
                return []
            if resp.status_code != 200:
                logger.warning(f"Reddit r/{subreddit} returned status {resp.status_code}")
                return []

            soup = BeautifulSoup(resp.content, "html.parser")
            entries = soup.find_all("entry")
            logger.info(f"r/{subreddit}: retrieved {len(entries)} raw RSS entries")

            for entry in entries:
                title = entry.find("title").get_text() if entry.find("title") else ""
                link = entry.find("link").get("href", "") if entry.find("link") else ""
                author_el = entry.find("author")
                author = author_el.find("name").get_text().replace("/u/", "").strip() if author_el and author_el.find("name") else ""
                content_raw = entry.find("content").get_text() if entry.find("content") else ""

                if not title or not link:
                    continue

                title_lower = title.lower()
                clean_text = BeautifulSoup(content_raw, "html.parser").get_text(separator="\n").strip()
                content_lower = clean_text.lower()

                # STRICT HIRING FILTER: Exclude candidate "FOR HIRE" resumes
                if title_lower.startswith("[for hire]") or "[for hire]" in title_lower or title_lower.startswith("[forhire]"):
                    continue
                if "seeking work" in title_lower or "available for hire" in title_lower:
                    continue

                # Must have positive hiring intent
                is_hiring = (
                    "[hiring]" in title_lower or
                    "hiring:" in title_lower or
                    "we're hiring" in title_lower or
                    "we are hiring" in title_lower or
                    "looking for" in title_lower or
                    "seeking developer" in title_lower or
                    "seeking engineer" in title_lower or
                    "[hiring]" in content_lower or
                    subreddit in ["startups", "pythonjobs", "golang"]
                )

                if not is_hiring:
                    continue

                # Pre-filter tech stack
                combined_text = f"{title}\n{clean_text}"
                if not check_pre_filter(title, combined_text):
                    # Check if contains core tech stack words
                    has_core_skills = any(k in combined_text.lower() for k in ["python", "golang", "go", "vue", "nuxt", "react", "typescript", "backend", "fullstack", "platform", "systems"])
                    if not has_core_skills:
                        continue

                # Founder detection
                is_founder = any(fk in combined_text.lower() for fk in FOUNDER_KEYWORDS)
                company_name = self._extract_company_name(title, author, is_founder, subreddit)

                # Direct contact options: emails, clean links, or direct Reddit PM link
                emails = EMAIL_REGEX.findall(clean_text)
                external_urls = URL_REGEX.findall(clean_text)
                clean_urls = [u for u in external_urls if "reddit.com" not in u and "redd.it" not in u and "imgur.com" not in u]

                # Generate direct Reddit PM link if author is known
                dm_link = f"https://reddit.com/message/compose/?to={author}&subject=Regarding%20{title[:40].replace(' ', '%20')}" if author else ""
                target_url = clean_urls[0] if clean_urls else (f"mailto:{emails[0]}" if emails else link)

                tech_tags = extract_tech_tags(combined_text)
                if is_founder and "Founder-Led" not in tech_tags:
                    tech_tags.insert(0, "Founder-Led")

                # Match post ID
                post_id = re.search(r'comments/([a-z0-9]+)/', link)
                external_id = f"reddit_{post_id.group(1)}" if post_id else f"reddit_{hash(link)}"

                # Append PM link in description if available
                desc_with_dm = combined_text
                if author and dm_link:
                    desc_with_dm = f"{combined_text}\n\n---\nDirect Outreach: Send Reddit PM to u/{author}: {dm_link}"

                posts.append({
                    "external_id": external_id,
                    "source": JobSource.REDDIT,
                    "source_url": link,
                    "company_name": company_name,
                    "job_title": title[:250],
                    "location_raw": "Remote",
                    "is_remote_or_relocation_friendly": True,
                    "description_raw": desc_with_dm,
                    "tech_stack_tags": tech_tags,
                    "is_founder_led": is_founder
                })

        except Exception as e:
            logger.error(f"Error fetching RSS for r/{subreddit}: {e}")
        return posts

    async def poll_all_subreddits(self) -> int:
        from app.workers.llm_tailor import tailor_job_task

        inserted_count = 0
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            for sub in TARGET_SUBREDDITS:
                logger.info(f"Checking Reddit r/{sub} for hiring opportunities...")
                posts = await self.fetch_subreddit_rss(client, sub)
                for p in posts:
                    async with AsyncSessionLocal() as session:
                        existing = await session.execute(
                            select(Job.id).where(Job.source_url == p["source_url"])
                        )
                        if existing.scalar_one_or_none() is None:
                            new_job = Job(
                                external_id=p["external_id"],
                                source=p["source"],
                                source_url=p["source_url"],
                                company_name=p["company_name"],
                                job_title=p["job_title"],
                                location_raw=p["location_raw"],
                                is_remote_or_relocation_friendly=p["is_remote_or_relocation_friendly"],
                                description_raw=p["description_raw"],
                                tech_stack_tags=p["tech_stack_tags"],
                                is_founder_led=p["is_founder_led"],
                                status=JobStatus.QUEUED_FOR_LLM
                            )
                            session.add(new_job)
                            await session.commit()
                            await session.refresh(new_job)
                            inserted_count += 1
                            logger.info(f"Queued Reddit job ({'FOUNDER-LED' if new_job.is_founder_led else 'HIRING'}): {new_job.job_title} ({new_job.id})")
                            tailor_job_task.delay(str(new_job.id))

                # Polite delay to respect Reddit's rate limit window
                await asyncio.sleep(3.0)

        logger.info(f"Reddit poll completed. Total qualified jobs inserted: {inserted_count}")
        return inserted_count


@celery_app.task(name="app.workers.reddit_listener.poll_reddit_hiring_task")
def poll_reddit_hiring_task() -> int:
    listener = RedditListener()
    return asyncio.run(listener.poll_all_subreddits())


if __name__ == "__main__":
    listener = RedditListener()
    asyncio.run(listener.poll_all_subreddits())
