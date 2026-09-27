import math
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, update, desc, asc, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from openai import OpenAI

from app.database import get_db
from app.models import Job, ApplicationAsset, JobStatus
from app.schemas import (
    JobResponse, JobWithAssetResponse, JobStatusUpdate,
    PaginatedJobsResponse, JobStatsResponse,
    CustomQuestionRequest, CustomQuestionResponse,
    HiringContactInfo, CoverLetterUpdateRequest, CoverLetterRegenerateRequest,
    ApplicationAssetResponse
)
from app.config import settings
from app.candidate_context import CANDIDATE_PROFILE, CANDIDATE_SYSTEM_PROMPT
from app.workers.llm_tailor import clamp_text
from app.utils.email_finder import extract_hiring_contacts
from app.utils.pdf_generator import generate_cover_letter_pdf

router = APIRouter(prefix="/jobs", tags=["Jobs"])


def build_job_with_asset_response(job: Job) -> JobWithAssetResponse:
    contacts = extract_hiring_contacts(
        description_raw=job.description_raw,
        company_name=job.company_name,
        source_url=job.source_url,
        job_title=job.job_title
    )
    hiring_contact_info = HiringContactInfo(**contacts)
    
    asset_resp = None
    if job.assets:
        asset_resp = ApplicationAssetResponse.model_validate(job.assets)

    return JobWithAssetResponse(
        id=job.id,
        external_id=job.external_id,
        source=job.source,
        source_url=job.source_url,
        company_name=job.company_name,
        job_title=job.job_title,
        location_raw=job.location_raw,
        is_remote_or_relocation_friendly=job.is_remote_or_relocation_friendly,
        description_raw=job.description_raw,
        tech_stack_tags=job.tech_stack_tags,
        match_score=job.match_score,
        match_reasoning=job.match_reasoning,
        status=job.status,
        is_founder_led=getattr(job, "is_founder_led", False),
        applied_at=job.applied_at,
        created_at=job.created_at,
        assets=asset_resp,
        hiring_contacts=hiring_contact_info
    )


@router.get("/stats", response_model=JobStatsResponse)
async def get_jobs_stats(
    days: Optional[int] = Query(None, description="Filter stats by date posted in last N days"),
    source: Optional[str] = Query(None, description="Filter stats by job source"),
    db: AsyncSession = Depends(get_db)
):
    query = select(Job.status, func.count(Job.id))
    filters = []
    if days is not None and days > 0:
        cutoff = datetime.utcnow() - timedelta(days=days)
        filters.append(Job.created_at >= cutoff)
    if source and source.lower() != "all":
        filters.append(Job.source == source.lower())

    if filters:
        query = query.where(*filters)

    query = query.group_by(Job.status)
    res = await db.execute(query)
    counts = dict(res.all())

    # Count founder-led postings
    founder_query = select(func.count(Job.id)).where(Job.is_founder_led.is_(True))
    if filters:
        founder_query = founder_query.where(*filters)
    founder_res = await db.execute(founder_query)
    founder_count = founder_res.scalar() or 0

    ready = counts.get(JobStatus.READY_TO_APPLY.value, 0)
    queued = counts.get(JobStatus.QUEUED_FOR_LLM.value, 0)
    applied = counts.get(JobStatus.APPLIED.value, 0)
    archived = counts.get(JobStatus.ARCHIVED.value, 0)
    total = sum(counts.values())

    return JobStatsResponse(
        ready_to_apply=ready,
        queued_for_llm=queued,
        applied=applied,
        archived=archived,
        founder_led=founder_count,
        total=total
    )


@router.get("", response_model=Union[PaginatedJobsResponse, List[JobWithAssetResponse]])
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter by status (ready_to_apply, queued_for_llm, applied, archived, all)"),
    source: Optional[str] = Query(None, description="Filter by source (greenhouse, lever, ashby, reddit, hackernews, all)"),
    founder_led_only: bool = Query(False, description="Filter for founder-led postings only"),
    min_score: int = Query(0, ge=0, le=100, description="Minimum match score"),
    days: Optional[int] = Query(None, ge=1, description="Filter jobs posted in last N days (1, 3, 7, 14, 30)"),
    sort_by: str = Query("score_desc", description="Sort order: 'score_desc', 'founder_first', 'date_desc', 'date_asc', 'score_asc', 'company_asc'"),
    search: Optional[str] = Query(None, description="Search keyword in title, company, or stack"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(50, ge=1, le=500, description="Items per page"),
    offset: Optional[int] = Query(None, ge=0, description="Legacy page offset (if provided, overrides page)"),
    paginate: bool = Query(True, description="Return paginated object with total count and metadata"),
    response: Response = None,
    db: AsyncSession = Depends(get_db)
):
    count_query = select(func.count(Job.id))
    items_query = select(Job).options(selectinload(Job.assets))

    filters = []

    # 1. Status filter
    if status and status.lower() != "all":
        filters.append(Job.status == status.lower())

    # 2. Source filter
    if source and source.lower() != "all":
        filters.append(Job.source == source.lower())

    # 3. Founder-led filter
    if founder_led_only:
        filters.append(Job.is_founder_led.is_(True))

    # 4. Min score filter
    if min_score > 0:
        filters.append(Job.match_score >= min_score)

    # 5. Date posted filter (days)
    if days is not None and days > 0:
        cutoff = datetime.utcnow() - timedelta(days=days)
        filters.append(Job.created_at >= cutoff)

    # 6. Keyword search
    if search and search.strip():
        kw = f"%{search.strip().lower()}%"
        filters.append(
            or_(
                func.lower(Job.company_name).like(kw),
                func.lower(Job.job_title).like(kw),
                func.lower(Job.location_raw).like(kw),
                func.lower(func.array_to_string(Job.tech_stack_tags, ' ')).like(kw)
            )
        )

    if filters:
        count_query = count_query.where(*filters)
        items_query = items_query.where(*filters)

    # Calculate total matching count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 7. Sorting
    if sort_by == "founder_first":
        items_query = items_query.order_by(desc(Job.is_founder_led), desc(Job.match_score), desc(Job.created_at))
    elif sort_by == "date_desc":
        items_query = items_query.order_by(desc(Job.created_at), desc(Job.match_score))
    elif sort_by == "date_asc":
        items_query = items_query.order_by(asc(Job.created_at), desc(Job.match_score))
    elif sort_by == "score_asc":
        items_query = items_query.order_by(asc(Job.match_score), desc(Job.created_at))
    elif sort_by == "company_asc":
        items_query = items_query.order_by(asc(Job.company_name), desc(Job.created_at))
    else:  # default: score_desc
        items_query = items_query.order_by(desc(Job.match_score), desc(Job.created_at))

    # Pagination calculation
    actual_offset = offset if offset is not None else (page - 1) * limit
    items_query = items_query.offset(actual_offset).limit(limit)

    result = await db.execute(items_query)
    raw_jobs = result.scalars().all()
    formatted_jobs = [build_job_with_asset_response(j) for j in raw_jobs]

    total_pages = max(1, math.ceil(total / limit)) if total > 0 else 1

    if response:
        response.headers["X-Total-Count"] = str(total)
        response.headers["X-Page"] = str(page)
        response.headers["X-Total-Pages"] = str(total_pages)

    if paginate:
        return PaginatedJobsResponse(
            items=formatted_jobs,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages
        )

    return formatted_jobs


@router.get("/{job_id}", response_model=JobWithAssetResponse)
async def get_job_by_id(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Job).options(selectinload(Job.assets)).where(Job.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found."
        )
    return build_job_with_asset_response(job)


@router.post("/{job_id}/status", response_model=JobResponse)
async def update_job_status(
    job_id: uuid.UUID,
    payload: JobStatusUpdate,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Job).where(Job.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found."
        )

    job.status = payload.status
    if payload.status == JobStatus.APPLIED and not job.applied_at:
        job.applied_at = datetime.utcnow()

    await db.commit()
    await db.refresh(job)
    return job


@router.post("/{job_id}/ignore", response_model=JobResponse)
async def ignore_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Job).where(Job.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found."
        )

    job.status = JobStatus.ARCHIVED
    await db.commit()
    await db.refresh(job)
    return job


@router.post("/{job_id}/unignore", response_model=JobResponse)
async def unignore_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Job).where(Job.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found."
        )

    job.status = JobStatus.READY_TO_APPLY if job.match_score >= 65 else JobStatus.NEW
    await db.commit()
    await db.refresh(job)
    return job


@router.put("/{job_id}/cover-letter", response_model=JobWithAssetResponse)
async def update_cover_letter(
    job_id: uuid.UUID,
    payload: CoverLetterUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Job).options(selectinload(Job.assets)).where(Job.id == job_id)
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found."
        )

    pdf_path = generate_cover_letter_pdf(
        candidate_name=CANDIDATE_PROFILE["name"],
        company_name=job.company_name,
        job_title=job.job_title,
        cover_letter_markdown=payload.cover_letter_markdown
    )

    if not job.assets:
        job.assets = ApplicationAsset(
            job_id=job.id,
            cover_letter_markdown=payload.cover_letter_markdown,
            cover_letter_pdf_path=pdf_path,
            ans_why_company_250=f"Excited by {job.company_name}'s high-scale mission.",
            ans_why_company_500=f"Excited by {job.company_name}'s mission and engineering culture.",
            ans_technical_challenge_250="Engineered 84%+ fraud reduction platform at Sycamore.",
            ans_technical_challenge_500="Engineered 84%+ fraud reduction platform at Sycamore and concurrent Golang backends.",
            ans_python_go_proficiency_220="5+ years building FastAPI systems & concurrent Golang microservices.",
            ans_location_relocation_220="Lagos, Nigeria based. Fully ready for remote or global relocation.",
            custom_qa={}
        )
        db.add(job.assets)
    else:
        job.assets.cover_letter_markdown = payload.cover_letter_markdown
        job.assets.cover_letter_pdf_path = pdf_path

    await db.commit()
    await db.refresh(job)
    return build_job_with_asset_response(job)


@router.post("/{job_id}/regenerate-cover-letter", response_model=JobWithAssetResponse)
async def regenerate_cover_letter(
    job_id: uuid.UUID,
    payload: CoverLetterRegenerateRequest,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Job).options(selectinload(Job.assets)).where(Job.id == job_id)
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found."
        )

    from app.workers.llm_tailor import LLMTailor
    tailor = LLMTailor()
    new_cover_letter = tailor.generate_role_customized_cover_letter(
        job_title=job.job_title,
        company_name=job.company_name,
        description=job.description_raw,
        archetype=payload.archetype or "auto",
        custom_instructions=payload.custom_instructions
    )

    pdf_path = generate_cover_letter_pdf(
        candidate_name=CANDIDATE_PROFILE["name"],
        company_name=job.company_name,
        job_title=job.job_title,
        cover_letter_markdown=new_cover_letter
    )

    if not job.assets:
        job.assets = ApplicationAsset(
            job_id=job.id,
            cover_letter_markdown=new_cover_letter,
            cover_letter_pdf_path=pdf_path,
            ans_why_company_250=f"Excited by {job.company_name}'s high-scale mission.",
            ans_why_company_500=f"Excited by {job.company_name}'s mission and engineering culture.",
            ans_technical_challenge_250="Engineered 84%+ fraud reduction platform at Sycamore.",
            ans_technical_challenge_500="Engineered 84%+ fraud reduction platform at Sycamore and concurrent Golang backends.",
            ans_python_go_proficiency_220="5+ years building FastAPI systems & concurrent Golang microservices.",
            ans_location_relocation_220="Lagos, Nigeria based. Fully ready for remote or global relocation.",
            custom_qa={}
        )
        db.add(job.assets)
    else:
        job.assets.cover_letter_markdown = new_cover_letter
        job.assets.cover_letter_pdf_path = pdf_path

    await db.commit()
    await db.refresh(job)
    return build_job_with_asset_response(job)


@router.post("/{job_id}/tailor", response_model=JobWithAssetResponse)
async def tailor_single_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    from app.workers.llm_tailor import LLMTailor
    tailor = LLMTailor()
    await tailor.tailor_job(str(job_id))
    stmt = select(Job).options(selectinload(Job.assets)).where(Job.id == job_id)
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found."
        )
    return job


@router.post("/tailor-pending")
async def tailor_pending_jobs(
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    from app.workers.llm_tailor import tailor_job_task
    stmt = select(Job.id).where(Job.status == JobStatus.QUEUED_FOR_LLM).limit(limit)
    res = await db.execute(stmt)
    job_ids = res.scalars().all()
    for jid in job_ids:
        tailor_job_task.delay(str(jid))
    return {"queued": len(job_ids), "message": f"Dispatched {len(job_ids)} jobs for tailoring."}


@router.post("/{job_id}/custom-question", response_model=CustomQuestionResponse)
async def answer_custom_question(
    job_id: uuid.UUID,
    payload: CustomQuestionRequest,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Job).options(selectinload(Job.assets)).where(Job.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found."
        )

    prompt = f"""
Target Job: {job.job_title} at {job.company_name}
Question: {payload.question}

Strict Instruction:
Generate a direct, highly competent, professional answer as Emmanuel Okeibunor.
Character Limit: EXACTLY <= {payload.max_chars} characters.
Do not exceed {payload.max_chars} characters under any circumstances!
"""

    answer_text = ""
    llm_key = settings.effective_llm_key
    if llm_key:
        try:
            base_url = settings.effective_base_url
            if base_url:
                client = OpenAI(api_key=llm_key, base_url=base_url)
            else:
                client = OpenAI(api_key=llm_key)

            response = client.chat.completions.create(
                model=settings.effective_model,
                messages=[
                    {"role": "system", "content": CANDIDATE_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=200
            )
            answer_text = response.choices[0].message.content.strip()
        except Exception as e:
            answer_text = f"Emmanuel brings proven experience scaling Vue/Nuxt & Python/Golang platforms at Sycamore (400k+ users) and ALN Riders."
    else:
        answer_text = f"Emmanuel brings proven experience scaling Vue/Nuxt & Python/Golang platforms at Sycamore (400k+ users) and ALN Riders."

    # Enforce clamp
    answer_text = clamp_text(answer_text, payload.max_chars)

    # Persist in custom_qa JSON field if asset exists
    if job.assets:
        qa_dict = dict(job.assets.custom_qa or {})
        qa_dict[payload.question] = answer_text
        job.assets.custom_qa = qa_dict
        await db.commit()

    return CustomQuestionResponse(
        job_id=job.id,
        question=payload.question,
        max_chars=payload.max_chars,
        char_count=len(answer_text),
        answer=answer_text
    )
