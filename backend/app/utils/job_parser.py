import csv
import io
import ipaddress
import json
import logging
import re
import socket
import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Job, JobSource, JobStatus
from app.schemas import IngestedJobItemResult, JobIngestResponse
from app.workers.ats_scraper import check_pre_filter, extract_tech_tags
from app.workers.llm_tailor import tailor_job_task

logger = logging.getLogger("job_parser")
logging.basicConfig(level=logging.INFO)

# SSRF Protection: Block loopback, private, link-local, multicast, reserved IPs
PRIVATE_IP_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def is_safe_url(url: str) -> bool:
    """Validate that URL is http/https and does not resolve to private or loopback IP addresses."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False

        if hostname.lower() in ("localhost", "127.0.0.1", "0.0.0.0", "metadata.google.internal"):
            return False

        ip_list = socket.getaddrinfo(hostname, None)
        for item in ip_list:
            ip_str = item[4][0]
            ip_obj = ipaddress.ip_address(ip_str)
            for net in PRIVATE_IP_NETWORKS:
                if ip_obj in net:
                    logger.warning(f"Blocked SSRF attempt to private network: {ip_str} ({url})")
                    return False
        return True
    except Exception as e:
        logger.warning(f"URL security validation failed for {url}: {e}")
        return False


def get_llm_client() -> Optional[OpenAI]:
    api_key = settings.effective_llm_key
    base_url = settings.effective_base_url
    if not api_key:
        return None
    try:
        if base_url:
            return OpenAI(api_key=api_key, base_url=base_url, max_retries=1)
        return OpenAI(api_key=api_key, max_retries=1)
    except Exception as e:
        logger.warning(f"Failed to create OpenAI client: {e}")
        return None


def clean_extracted_text(text: str) -> str:
    """Normalize whitespace and strip HTML/formatting noise."""
    if not text:
        return ""
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_metadata_with_llm(raw_text: str, fallback_title: str = "Software Engineer", fallback_company: str = "Company") -> Dict[str, Any]:
    """Use configured LLM (DeepSeek / Gemini / OpenAI) to extract structured job details from raw text."""
    client = get_llm_client()
    if not client:
        return heuristic_extract_metadata(raw_text, fallback_title, fallback_company)

    prompt = f"""You are a high-precision job parsing engine. Analyze the following job posting text and extract the key fields into clean JSON.

TEXT TO PARSE:
\"\"\"
{raw_text[:4000]}
\"\"\"

Return ONLY valid JSON matching this exact schema:
{{
  "job_title": "string (the exact job title, e.g. Senior Backend Engineer)",
  "company_name": "string (company or organization name)",
  "location": "string (city/country or Remote)",
  "description": "string (comprehensive job description, responsibilities, requirements. Do not truncate essential parts)",
  "tech_stack_tags": ["list", "of", "technologies", "detected"]
}}
"""
    try:
        response = client.chat.completions.create(
            model=settings.effective_model,
            messages=[
                {"role": "system", "content": "You are a professional recruiting parser that returns strict JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=1500
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        title = data.get("job_title") or fallback_title
        company = data.get("company_name") or fallback_company
        location = data.get("location") or "Remote"
        description = data.get("description") or raw_text
        tags = data.get("tech_stack_tags") or extract_tech_tags(f"{title} {description}")
        return {
            "job_title": title.strip(),
            "company_name": company.strip(),
            "location_raw": location.strip(),
            "description_raw": clean_extracted_text(description),
            "tech_stack_tags": tags
        }
    except Exception as e:
        logger.warning(f"LLM extraction error: {e}. Falling back to heuristics.")
        return heuristic_extract_metadata(raw_text, fallback_title, fallback_company)


def heuristic_extract_metadata(raw_text: str, fallback_title: str = "Software Engineer", fallback_company: str = "Company") -> Dict[str, Any]:
    """Heuristic regex parsing for job title, company, location when LLM is unavailable."""
    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
    title = fallback_title
    company = fallback_company
    location = "Remote"

    # Search for common label patterns
    for line in lines[:15]:
        lower = line.lower()
        if re.match(r"^(job\s*title|role|position)\s*[:\-]\s*", lower):
            title = re.sub(r"^(job\s*title|role|position)\s*[:\-]\s*", "", line, flags=re.I).strip()
        elif re.match(r"^(company|organization|employer)\s*[:\-]\s*", lower):
            company = re.sub(r"^(company|organization|employer)\s*[:\-]\s*", "", line, flags=re.I).strip()
        elif re.match(r"^(location|workplace|city)\s*[:\-]\s*", lower):
            location = re.sub(r"^(location|workplace|city)\s*[:\-]\s*", "", line, flags=re.I).strip()

    # If title still default, check first line
    if title == fallback_title and lines:
        first_line = lines[0]
        if len(first_line) < 80 and not any(k in first_line.lower() for k in ["about us", "overview", "description"]):
            # e.g. "Senior Frontend Developer at Stripe"
            at_match = re.search(r"^(.*?)\s+(?:at|@)\s+(.*)$", first_line, re.I)
            if at_match:
                title = at_match.group(1).strip()
                if company == fallback_company:
                    company = at_match.group(2).strip()
            else:
                title = first_line

    tags = extract_tech_tags(f"{title} {raw_text}")
    return {
        "job_title": title,
        "company_name": company,
        "location_raw": location,
        "description_raw": clean_extracted_text(raw_text),
        "tech_stack_tags": tags
    }


def parse_pdf_bytes(file_bytes: bytes, filename: str = "job.pdf") -> List[Dict[str, Any]]:
    """Extract text from PDF file and parse job details."""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        extracted_pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                extracted_pages.append(text)
        full_text = "\n\n".join(extracted_pages).strip()
        if not full_text:
            raise ValueError("No readable text found in PDF document.")

        parsed = extract_metadata_with_llm(
            raw_text=full_text,
            fallback_title=filename.replace(".pdf", "").replace("_", " ").title(),
            fallback_company="Direct Upload"
        )
        parsed["source"] = JobSource.MANUAL
        parsed["source_url"] = f"manual://pdf/{uuid.uuid4().hex[:12]}/{filename}"
        return [parsed]
    except Exception as e:
        logger.error(f"Error parsing PDF {filename}: {e}")
        raise ValueError(f"Failed to parse PDF document: {str(e)}")


def _fuzzy_get_col(row: Dict[str, Any], candidates: List[str]) -> Optional[str]:
    """Find column value from a row dict ignoring case and spaces."""
    normalized_row = {re.sub(r"[_\s\-]+", "", k.lower()): v for k, v in row.items() if k is not None}
    for candidate in candidates:
        clean_cand = re.sub(r"[_\s\-]+", "", candidate.lower())
        if clean_cand in normalized_row and normalized_row[clean_cand] is not None:
            val = str(normalized_row[clean_cand]).strip()
            if val:
                return val
    return None


def parse_csv_bytes(file_bytes: bytes, filename: str = "jobs.csv") -> List[Dict[str, Any]]:
    """Parse jobs from CSV file with flexible column matching."""
    decoded_text = ""
    for encoding in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            decoded_text = file_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if not decoded_text:
        raise ValueError("Could not decode CSV file contents with supported encodings.")

    f = io.StringIO(decoded_text)
    reader = csv.DictReader(f)
    if not reader.fieldnames:
        raise ValueError("CSV file has no headers.")

    jobs_found: List[Dict[str, Any]] = []

    title_cols = ["title", "job_title", "job title", "role", "position", "headline", "job"]
    company_cols = ["company", "company_name", "company name", "organization", "org", "employer", "firm"]
    desc_cols = ["description", "job_description", "job description", "details", "responsibilities", "summary", "body", "text", "content"]
    url_cols = ["url", "link", "source_url", "source url", "job_url", "job url", "apply_url", "apply link"]
    loc_cols = ["location", "city", "country", "workplace", "workplace_type", "remote"]
    tag_cols = ["tags", "tech_stack", "technologies", "skills", "stack"]

    for row_idx, row in enumerate(reader, start=1):
        # Skip completely empty rows
        if not any(row.values()):
            continue

        title = _fuzzy_get_col(row, title_cols) or f"Role #{row_idx}"
        company = _fuzzy_get_col(row, company_cols) or "Imported Opportunity"
        desc = _fuzzy_get_col(row, desc_cols) or ""
        url = _fuzzy_get_col(row, url_cols)
        location = _fuzzy_get_col(row, loc_cols) or "Remote"
        tags_raw = _fuzzy_get_col(row, tag_cols)

        # If description is missing but another column has long text, use it
        if not desc:
            longest_val = max((str(v).strip() for v in row.values() if v), key=len, default="")
            if len(longest_val) > 50:
                desc = longest_val
            else:
                desc = f"{title} at {company}. Location: {location}."

        tags: List[str] = []
        if tags_raw:
            tags = [t.strip() for t in re.split(r"[,;|]+", tags_raw) if t.strip()]
        if not tags:
            tags = extract_tech_tags(f"{title} {desc}")

        if not url:
            url = f"manual://csv/{uuid.uuid4().hex[:12]}/{row_idx}"

        jobs_found.append({
            "job_title": title,
            "company_name": company,
            "location_raw": location,
            "description_raw": clean_extracted_text(desc),
            "tech_stack_tags": tags,
            "source_url": url,
            "source": JobSource.MANUAL
        })

    if not jobs_found:
        raise ValueError("No valid job rows found in CSV.")

    return jobs_found


def parse_xlsx_bytes(file_bytes: bytes, filename: str = "jobs.xlsx") -> List[Dict[str, Any]]:
    """Parse jobs from Excel (.xlsx) file."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        sheet = wb.active
        if not sheet:
            raise ValueError("Excel file contains no active worksheet.")

        rows = list(sheet.iter_rows(values_only=True))
        if len(rows) < 2:
            raise ValueError("Excel sheet contains fewer than 2 rows (header + data required).")

        headers = [str(cell).strip() if cell is not None else f"col_{idx}" for idx, cell in enumerate(rows[0])]
        
        # Build CSV-like row dicts
        dict_rows = []
        for r in rows[1:]:
            if not any(cell is not None for cell in r):
                continue
            row_dict = {}
            for col_idx, header in enumerate(headers):
                val = r[col_idx] if col_idx < len(r) else None
                row_dict[header] = str(val).strip() if val is not None else ""
            dict_rows.append(row_dict)

        # Map using same fuzzy column detection
        jobs_found: List[Dict[str, Any]] = []
        title_cols = ["title", "job_title", "job title", "role", "position", "headline", "job"]
        company_cols = ["company", "company_name", "company name", "organization", "org", "employer", "firm"]
        desc_cols = ["description", "job_description", "job description", "details", "responsibilities", "summary", "body", "text", "content"]
        url_cols = ["url", "link", "source_url", "source url", "job_url", "job url", "apply_url", "apply link"]
        loc_cols = ["location", "city", "country", "workplace", "workplace_type", "remote"]
        tag_cols = ["tags", "tech_stack", "technologies", "skills", "stack"]

        for row_idx, row in enumerate(dict_rows, start=1):
            title = _fuzzy_get_col(row, title_cols) or f"Role #{row_idx}"
            company = _fuzzy_get_col(row, company_cols) or "Imported Opportunity"
            desc = _fuzzy_get_col(row, desc_cols) or ""
            url = _fuzzy_get_col(row, url_cols)
            location = _fuzzy_get_col(row, loc_cols) or "Remote"
            tags_raw = _fuzzy_get_col(row, tag_cols)

            if not desc:
                longest_val = max((str(v).strip() for v in row.values() if v), key=len, default="")
                if len(longest_val) > 50:
                    desc = longest_val
                else:
                    desc = f"{title} at {company}. Location: {location}."

            tags: List[str] = []
            if tags_raw:
                tags = [t.strip() for t in re.split(r"[,;|]+", tags_raw) if t.strip()]
            if not tags:
                tags = extract_tech_tags(f"{title} {desc}")

            if not url:
                url = f"manual://xlsx/{uuid.uuid4().hex[:12]}/{row_idx}"

            jobs_found.append({
                "job_title": title,
                "company_name": company,
                "location_raw": location,
                "description_raw": clean_extracted_text(desc),
                "tech_stack_tags": tags,
                "source_url": url,
                "source": JobSource.MANUAL
            })

        if not jobs_found:
            raise ValueError("No valid job rows found in Excel sheet.")

        return jobs_found
    except Exception as e:
        logger.error(f"Error parsing Excel file {filename}: {e}")
        raise ValueError(f"Failed to parse Excel file: {str(e)}")


async def scrape_job_from_url(url: str) -> Dict[str, Any]:
    """Scrape and parse job posting from any URL (Greenhouse, Lever, Ashby, or generic web page)."""
    clean_url = url.strip()
    if not is_safe_url(clean_url):
        raise ValueError(f"URL security check failed or invalid scheme: {clean_url}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9"
    }

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        # Check Greenhouse direct API pattern
        # e.g. https://boards.greenhouse.io/<company>/jobs/<id> or https://job-boards.greenhouse.io/<company>/jobs/<id>
        gh_match = re.search(r"(?:boards|job-boards)\.greenhouse\.io/(?:embed/job_app\?for=)?([^/]+)/jobs/(\d+)", clean_url)
        if gh_match:
            slug, job_id = gh_match.group(1), gh_match.group(2)
            api_url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{job_id}?content=true"
            try:
                resp = await client.get(api_url, headers={"Accept": "application/json"})
                if resp.status_code == 200:
                    data = resp.json()
                    title = data.get("title", "").strip()
                    loc_obj = data.get("location", {})
                    location = loc_obj.get("name", "Remote") if isinstance(loc_obj, dict) else str(loc_obj)
                    raw_html = data.get("content", "")
                    desc = BeautifulSoup(raw_html, "html.parser").get_text(separator="\n").strip()
                    return {
                        "job_title": title,
                        "company_name": slug.replace("-", " ").title(),
                        "location_raw": location or "Remote",
                        "description_raw": clean_extracted_text(desc),
                        "tech_stack_tags": extract_tech_tags(f"{title} {desc}"),
                        "source_url": clean_url,
                        "source": JobSource.GREENHOUSE
                    }
            except Exception as e:
                logger.warning(f"Greenhouse direct API fetch failed: {e}. Falling back to HTML scrape.")

        # Check Lever direct API pattern: https://jobs.lever.co/<company>/<id>
        lever_match = re.search(r"jobs\.lever\.co/([^/]+)/([a-f0-9\-]+)", clean_url)
        if lever_match:
            slug, job_id = lever_match.group(1), lever_match.group(2)
            api_url = f"https://api.lever.co/v0/postings/{slug}/{job_id}"
            try:
                resp = await client.get(api_url, headers={"Accept": "application/json"})
                if resp.status_code == 200:
                    data = resp.json()
                    title = data.get("text", "").strip()
                    categories = data.get("categories", {})
                    location = categories.get("location", "Remote") if isinstance(categories, dict) else "Remote"
                    raw_desc = data.get("descriptionPlain", "") or data.get("description", "")
                    desc = BeautifulSoup(raw_desc, "html.parser").get_text(separator="\n").strip()
                    return {
                        "job_title": title,
                        "company_name": slug.replace("-", " ").title(),
                        "location_raw": location or "Remote",
                        "description_raw": clean_extracted_text(desc),
                        "tech_stack_tags": extract_tech_tags(f"{title} {desc}"),
                        "source_url": clean_url,
                        "source": JobSource.LEVER
                    }
            except Exception as e:
                logger.warning(f"Lever direct API fetch failed: {e}. Falling back to HTML scrape.")

        # Generic web page scrape
        resp = await client.get(clean_url, headers=headers)
        if resp.status_code >= 400:
            raise ValueError(f"HTTP error {resp.status_code} when fetching {clean_url}")

        soup = BeautifulSoup(resp.text, "html.parser")

        # Strip noise elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "svg", "form"]):
            tag.decompose()

        # Extract title candidates
        og_title = ""
        og_title_tag = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "twitter:title"})
        if og_title_tag and og_title_tag.get("content"):
            og_title = og_title_tag["content"].strip()

        page_title = soup.title.get_text().strip() if soup.title else ""
        h1_tag = soup.find("h1")
        h1_text = h1_tag.get_text().strip() if h1_tag else ""

        raw_title = og_title or h1_text or page_title or "Job Opportunity"

        # Extract company candidates
        og_site_tag = soup.find("meta", property="og:site_name")
        og_site = og_site_tag["content"].strip() if og_site_tag and og_site_tag.get("content") else ""
        domain = urlparse(clean_url).netloc.split(":")[0]
        domain_name = domain.split(".")[-2].title() if len(domain.split(".")) >= 2 else domain

        company_candidate = og_site or domain_name

        # Extract body text
        main_content = soup.find(["main", "article"]) or soup.find(class_=re.compile(r"job[-_]?desc|posting|content|description", re.I)) or soup.body
        body_text = main_content.get_text(separator="\n") if main_content else soup.get_text(separator="\n")
        cleaned_body = clean_extracted_text(body_text)

        # Use LLM extraction to get accurate title, company, description, and stack
        extracted = extract_metadata_with_llm(
            raw_text=f"PAGE TITLE: {raw_title}\nDOMAIN: {domain_name}\n\nPAGE CONTENT:\n{cleaned_body}",
            fallback_title=raw_title,
            fallback_company=company_candidate
        )

        # Detect source ATS from URL
        detected_source = JobSource.MANUAL
        if "greenhouse.io" in clean_url:
            detected_source = JobSource.GREENHOUSE
        elif "lever.co" in clean_url:
            detected_source = JobSource.LEVER
        elif "ashbyhq.com" in clean_url:
            detected_source = JobSource.ASHBY
        elif "workable.com" in clean_url:
            detected_source = JobSource.WORKABLE

        extracted["source_url"] = clean_url
        extracted["source"] = detected_source
        return extracted


def parse_raw_text_input(
    raw_text: str,
    override_title: Optional[str] = None,
    override_company: Optional[str] = None,
    override_location: Optional[str] = None,
    source_url: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Parse pasted text containing one or multiple job postings."""
    clean_text = clean_extracted_text(raw_text)
    if not clean_text:
        raise ValueError("Job text cannot be empty.")

    # Check for multi-job delimiters (e.g. "---" or "====")
    sections = re.split(r"\n\s*[-=]{3,}\s*\n", clean_text)
    sections = [s.strip() for s in sections if len(s.strip()) > 30]

    if len(sections) > 1 and not (override_title and override_company):
        results = []
        for idx, sec in enumerate(sections, start=1):
            meta = extract_metadata_with_llm(sec, fallback_title=f"Position #{idx}", fallback_company="Imported Opportunity")
            meta["source_url"] = f"manual://paste/{uuid.uuid4().hex[:12]}/{idx}"
            meta["source"] = JobSource.MANUAL
            results.append(meta)
        return results

    # Single job posting
    if override_title and override_company:
        tags = extract_tech_tags(f"{override_title} {clean_text}")
        return [{
            "job_title": override_title.strip(),
            "company_name": override_company.strip(),
            "location_raw": override_location.strip() if override_location else "Remote",
            "description_raw": clean_text,
            "tech_stack_tags": tags,
            "source_url": source_url or f"manual://paste/{uuid.uuid4().hex[:12]}",
            "source": JobSource.MANUAL
        }]

    # Auto-extract title & company using LLM or heuristics
    meta = extract_metadata_with_llm(
        clean_text,
        fallback_title=override_title or "Software Engineer",
        fallback_company=override_company or "Company"
    )
    if override_location:
        meta["location_raw"] = override_location
    meta["source_url"] = source_url or f"manual://paste/{uuid.uuid4().hex[:12]}"
    meta["source"] = JobSource.MANUAL
    return [meta]


async def execute_job_ingest_pipeline(
    jobs_data: List[Dict[str, Any]],
    bypass_filter: bool,
    tailor_now: bool,
    session: AsyncSession
) -> JobIngestResponse:
    """Core ingestion engine: deduplicates, pre-filters, inserts jobs, and triggers LLM tailoring."""
    results: List[IngestedJobItemResult] = []
    total_received = len(jobs_data)
    total_processed = 0
    total_queued = 0
    total_duplicates = 0
    total_rejected = 0

    for item in jobs_data:
        job_title = item.get("job_title", "").strip() or "Untitled Role"
        company_name = item.get("company_name", "").strip() or "Unknown Company"
        description = item.get("description_raw", "").strip()
        location_raw = item.get("location_raw", "Remote")
        source_url = item.get("source_url") or f"manual://{uuid.uuid4().hex}"
        source = item.get("source", JobSource.MANUAL)
        tech_tags = item.get("tech_stack_tags") or extract_tech_tags(f"{job_title} {description}")

        if not description:
            results.append(IngestedJobItemResult(
                job_title=job_title,
                company_name=company_name,
                source_url=source_url,
                status="rejected",
                action_taken="error",
                error_message="Job description is required and cannot be empty."
            ))
            total_rejected += 1
            continue

        # 1. Deduplication check by source_url
        dup_stmt = select(Job).where(Job.source_url == source_url)
        dup_res = await session.execute(dup_stmt)
        existing_job = dup_res.scalar_one_or_none()

        if existing_job:
            results.append(IngestedJobItemResult(
                id=existing_job.id,
                job_title=existing_job.job_title,
                company_name=existing_job.company_name,
                source_url=existing_job.source_url,
                status=existing_job.status.value,
                match_score=existing_job.match_score,
                action_taken="duplicate_skipped",
                error_message=f"Job already exists in queue (Status: {existing_job.status.value})."
            ))
            total_duplicates += 1
            continue

        # 2. Keyword pre-filter check (can be bypassed for manual user uploads)
        if not bypass_filter:
            if not check_pre_filter(job_title, description):
                results.append(IngestedJobItemResult(
                    job_title=job_title,
                    company_name=company_name,
                    source_url=source_url,
                    status="rejected",
                    action_taken="filter_rejected",
                    error_message="Filtered out: title or description did not match target keyword criteria."
                ))
                total_rejected += 1
                continue

        # 3. Create Job Record
        new_job = Job(
            external_id=f"manual-{uuid.uuid4().hex[:8]}",
            source=source,
            source_url=source_url,
            company_name=company_name,
            job_title=job_title,
            location_raw=location_raw,
            is_remote_or_relocation_friendly=True,
            description_raw=description,
            tech_stack_tags=tech_tags,
            status=JobStatus.QUEUED_FOR_LLM,
            match_score=0
        )
        session.add(new_job)
        await session.commit()
        await session.refresh(new_job)

        total_processed += 1
        total_queued += 1

        # 4. Trigger Celery LLM Tailoring Task
        if tailor_now:
            try:
                tailor_job_task.delay(str(new_job.id))
                logger.info(f"Dispatched Celery LLM tailoring for ingested job: {new_job.id}")
            except Exception as e:
                logger.error(f"Failed to dispatch Celery task for {new_job.id}: {e}")

        results.append(IngestedJobItemResult(
            id=new_job.id,
            job_title=new_job.job_title,
            company_name=new_job.company_name,
            source_url=new_job.source_url,
            status=new_job.status.value,
            match_score=new_job.match_score,
            action_taken="queued_for_llm"
        ))

    return JobIngestResponse(
        total_received=total_received,
        total_processed=total_processed,
        total_queued=total_queued,
        total_duplicates=total_duplicates,
        total_rejected=total_rejected,
        results=results
    )
