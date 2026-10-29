import math
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status, UploadFile, File, Form
from sqlalchemy import select, update, desc, asc, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from openai import OpenAI

from app.database import get_db
from app.models import Job, ApplicationAsset, JobStatus
from app.schemas import (
    BulkJobRequest, JobResponse, JobWithAssetResponse, JobStatusUpdate,
    PaginatedJobsResponse, JobStatsResponse,
    CustomQuestionRequest, CustomQuestionResponse,
    HiringContactInfo, CoverLetterUpdateRequest, CoverLetterRegenerateRequest,
    ResumeUpdateRequest, ResumeRegenerateRequest,
    ApplicationAssetResponse, OutreachRequest, OutreachResponse,
    JobIngestUrlsRequest, JobIngestTextRequest, JobIngestResponse, IngestedJobItemResult
)
from app.config import settings
from app.services.candidate_profile import application_context, legacy_context
from app.workers.llm_tailor import clamp_text
from app.utils.email_finder import extract_hiring_contacts
from app.utils.job_parser import (
    parse_pdf_bytes,
    parse_csv_bytes,
    parse_xlsx_bytes,
    scrape_job_from_url,
    parse_raw_text_input,
    execute_job_ingest_pipeline,
)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


def build_job_with_asset_response(job: Job) -> JobWithAssetResponse:
    contacts = extract_hiring_contacts(
        description_raw=job.description_raw,
        company_name=job.company_name,
        source_url=job.source_url,
        job_title=job.job_title,
        candidate=(getattr(job.assets, "candidate_snapshot", None) or {}).get("data", {})
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
        organization_type=job.organization_type,
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
    organization_type: Optional[str] = Query(None, pattern="^(nonprofit|unknown)$"),
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

    if organization_type:
        filters.append(Job.organization_type == organization_type)

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


@router.post("/bulk")
async def bulk_jobs(payload: BulkJobRequest, db: AsyncSession = Depends(get_db)):
    from app.workers.llm_tailor import tailor_job_task

    ids = list(dict.fromkeys(payload.job_ids))
    result = await db.execute(select(Job).where(Job.id.in_(ids)).order_by(Job.id).with_for_update())
    jobs = {job.id: job for job in result.scalars().all()}
    updated, skipped, previous = [], [], {}
    for job_id in ids:
        job = jobs.get(job_id)
        reason = None
        if not job:
            reason = "Job no longer exists."
        elif payload.action == "ignore":
            if job.status not in (JobStatus.NEW, JobStatus.READY_TO_APPLY):
                reason = "Only unsubmitted jobs that are not being prepared can be ignored in bulk."
            else:
                previous[str(job.id)] = job.status.value
                job.status = JobStatus.ARCHIVED
        elif payload.action == "restore":
            prior = payload.previous_statuses.get(job_id)
            if job.status != JobStatus.ARCHIVED or prior not in (JobStatus.NEW, JobStatus.READY_TO_APPLY):
                reason = "Job changed since it was ignored; it was left unchanged."
            else:
                job.status = prior
        elif payload.action == "mark_applied":
            if job.status != JobStatus.READY_TO_APPLY:
                reason = "Only jobs with materials ready can be marked applied in bulk."
            else:
                job.status = JobStatus.APPLIED
                job.applied_at = job.applied_at or datetime.utcnow()
        elif payload.action == "prepare":
            if job.status != JobStatus.NEW:
                reason = "Only jobs without prepared materials can be queued."
            else:
                job.status = JobStatus.QUEUED_FOR_LLM
        if reason:
            skipped.append({"id": str(job_id), "reason": reason})
        else:
            updated.append(str(job_id))
    await db.commit()
    if payload.action == "prepare":
        queued = []
        for job_id in updated:
            try:
                tailor_job_task.delay(job_id)
                queued.append(job_id)
            except Exception:
                # Release only our reservation so the user can retry a broker failure.
                await db.execute(update(Job).where(Job.id == uuid.UUID(job_id), Job.status == JobStatus.QUEUED_FOR_LLM).values(status=JobStatus.NEW))
                await db.commit()
                skipped.append({"id": job_id, "reason": "Could not queue materials. Please retry."})
        updated = queued
    return {"updated_ids": updated, "skipped": skipped, "previous_statuses": previous}


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

    context = await application_context(db, job.assets) if not job.assets else None

    # Invalidate the cached PDF; the download endpoint renders the latest markdown.
    pdf_path = None

    if not job.assets:
        job.assets = ApplicationAsset(
            job_id=job.id,
            candidate_snapshot=context.snapshot(),
            cover_letter_markdown=payload.cover_letter_markdown,
            cover_letter_pdf_path=pdf_path,
            ans_why_company_250=f"Excited by {job.company_name}'s high-scale mission.",
            ans_why_company_500=f"Excited by {job.company_name}'s mission and engineering culture.",
            ans_technical_challenge_250="Not provided.",
            ans_technical_challenge_500="Not provided.",
            ans_python_go_proficiency_220="Not provided.",
            ans_location_relocation_220="Not provided.",
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

    context = await application_context(db, job.assets)
    from app.workers.llm_tailor import LLMTailor
    tailor = LLMTailor(context)
    new_cover_letter = tailor.generate_role_customized_cover_letter(
        job_title=job.job_title,
        company_name=job.company_name,
        description=job.description_raw,
        archetype=payload.archetype or "auto",
        custom_instructions=payload.custom_instructions
    )

    # Invalidate the cached PDF; the download endpoint renders the latest markdown.
    pdf_path = None

    if not job.assets:
        job.assets = ApplicationAsset(
            job_id=job.id,
            candidate_snapshot=context.snapshot(),
            cover_letter_markdown=new_cover_letter,
            cover_letter_pdf_path=pdf_path,
            ans_why_company_250=f"Excited by {job.company_name}'s high-scale mission.",
            ans_why_company_500=f"Excited by {job.company_name}'s mission and engineering culture.",
            ans_technical_challenge_250="Not provided.",
            ans_technical_challenge_500="Not provided.",
            ans_python_go_proficiency_220="Not provided.",
            ans_location_relocation_220="Not provided.",
            custom_qa={}
        )
        db.add(job.assets)
    else:
        job.assets.cover_letter_markdown = new_cover_letter
        job.assets.cover_letter_pdf_path = pdf_path

    await db.commit()
    await db.refresh(job)
    return build_job_with_asset_response(job)


@router.put("/{job_id}/resume", response_model=JobWithAssetResponse)
async def update_resume(
    job_id: uuid.UUID,
    payload: ResumeUpdateRequest,
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

    context = await application_context(db, job.assets) if not job.assets else None

    # Invalidate the cached PDF; the download endpoint renders the latest markdown.
    pdf_path = None

    if not job.assets:
        job.assets = ApplicationAsset(
            job_id=job.id,
            candidate_snapshot=context.snapshot(),
            cover_letter_markdown="Not generated yet",
            resume_markdown=payload.resume_markdown,
            resume_pdf_path=pdf_path,
            ans_why_company_250="Excited by company mission.",
            ans_why_company_500="Excited by company mission.",
            ans_technical_challenge_250="N/A",
            ans_technical_challenge_500="N/A",
            ans_python_go_proficiency_220="N/A",
            ans_location_relocation_220="N/A",
            custom_qa={}
        )
        db.add(job.assets)
    else:
        job.assets.resume_markdown = payload.resume_markdown
        job.assets.resume_pdf_path = pdf_path

    await db.commit()
    await db.refresh(job)
    return build_job_with_asset_response(job)


@router.post("/{job_id}/regenerate-resume", response_model=JobWithAssetResponse)
async def regenerate_resume(
    job_id: uuid.UUID,
    payload: ResumeRegenerateRequest,
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

    context = await application_context(db, job.assets)
    llm_key = settings.effective_llm_key
    if not llm_key:
        raise HTTPException(status_code=400, detail="No LLM API key configured.")

    base_url = settings.effective_base_url
    client = OpenAI(api_key=llm_key, base_url=base_url) if base_url else OpenAI(api_key=llm_key)

    system_prompt = f"{context.system_prompt}\n\nMASTER RESUME:\n{context.resume}"
    prompt = f"""
Analyze the following job opportunity and tailor the master resume for {context.name}.

Target Job:
Company: {job.company_name}
Title: {job.job_title}
Job Description:
{job.description_raw}
Custom Directives: {payload.custom_instructions or "None"}

Strict Rules:
- Output ONLY the raw ATS-optimized markdown for the resume.
- Use exact-match keywords from the job description.
- Spell out acronyms at least once alongside short form.
- Use reverse-chronological order and action-driven bullet points.
- Standard section headings only.
"""
    try:
        response = client.chat.completions.create(
            model=settings.effective_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2500
        )
        new_resume_markdown = response.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Generation failed: {str(e)}")

    # Invalidate the cached PDF; the download endpoint renders the latest markdown.
    pdf_path = None

    if not job.assets:
        job.assets = ApplicationAsset(
            job_id=job.id,
            candidate_snapshot=context.snapshot(),
            cover_letter_markdown="Not generated yet",
            resume_markdown=new_resume_markdown,
            resume_pdf_path=pdf_path,
            ans_why_company_250="Excited by company mission.",
            ans_why_company_500="Excited by company mission.",
            ans_technical_challenge_250="N/A",
            ans_technical_challenge_500="N/A",
            ans_python_go_proficiency_220="N/A",
            ans_location_relocation_220="N/A",
            custom_qa={}
        )
        db.add(job.assets)
    else:
        job.assets.resume_markdown = new_resume_markdown
        job.assets.resume_pdf_path = pdf_path

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

    context = await application_context(db, job.assets)
    prompt = f"""
Target Job: {job.job_title} at {job.company_name}
Question: {payload.question}

Strict Instruction:
Generate a direct, highly competent, professional answer as {context.name}.
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
                    {"role": "system", "content": context.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=200
            )
            answer_text = response.choices[0].message.content.strip()
        except Exception as e:
            answer_text = "Automated answering is unavailable. Please answer this question using your confirmed experience."
    else:
        answer_text = "Automated answering is unavailable. Please answer this question using your confirmed experience."

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


@router.post("/{job_id}/outreach", response_model=OutreachResponse)
async def generate_outreach_message(
    job_id: uuid.UUID,
    payload: OutreachRequest,
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

    llm_key = settings.effective_llm_key
    if not llm_key:
        raise HTTPException(status_code=400, detail="No LLM API key configured.")

    base_url = settings.effective_base_url
    client = OpenAI(api_key=llm_key, base_url=base_url) if base_url else OpenAI(api_key=llm_key)

    context = await application_context(db, job.assets)
    prompt = f"""
# Role & Objective
You are an elite executive recruiter and technical cold-outreach strategist. Your goal is to write an ultra-concise, high-reply-rate outreach email to a {payload.recipient_persona} regarding the {job.job_title} role at {job.company_name}.

Target Company: {job.company_name}
Target Role: {job.job_title}
Job Description:
{job.description_raw}

# Candidate Profile
{context.system_prompt}

# Core Constraints
- **Word Count:** Strictly 75 to 125 words (excluding subject line and signature). Every sentence must earn its place.
- **Formatting:** Short paragraphs (1–2 sentences max). Use at most 2–3 concise bullet points if highlighting technical proof.
- **Zero Fluff:** Never start with "I hope this email finds you well," "My name is...", or "I am writing to express my interest." Jump straight into context in sentence 1.

# Routing Context
Recipient Persona: {payload.recipient_persona}
- If `technical_lead`: Speak peer-to-peer. Focus on system architecture, tech stack overlap, shipping velocity, and production metrics. Skip HR buzzwords.
- If `recruiter`: Make their screening job effortless. Highlight exact years of experience, core stack match from the JD, and immediate fit.
- If `founder`: Focus on product ownership, business impact (revenue, retention, cost reduction, speed to market), and end-to-end execution.

Outreach Stage: {payload.outreach_type}
- If `post_application`: Mention you just submitted an application for the role and wanted to share a quick note on why your background is a direct match.
- If `direct_pitch`: Pitch value directly around a recent company milestone, product launch, or engineering challenge without referencing an application portal.
- If `follow_up`: Keep under 60 words. Reply-thread style. Gently bump the previous note and add one new micro-insight or link to a live project/GitHub repo.

# Structure
1. Subject Lines (Generate exactly 2 options).
2. The Context Hook (1 natural sentence).
3. The "Already Built This" Proof (1-2 hard-hitting, quantified wins connecting JD priority to candidate profile).
4. Low-Friction CTA (A question that does not ask for a 30-min call).
5. Signature Block:
{context.name}
{context.data.get("headline", "")}
{context.data.get("contact", {})}

Respond EXACTLY with this JSON structure:
{{
    "subject_1": "Subject option 1",
    "subject_2": "Subject option 2",
    "body": "The full outreach message body including the signature"
}}
"""

    try:
        response = client.chat.completions.create(
            model=settings.effective_model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=500
        )
        import json
        raw_json = response.choices[0].message.content or "{}"
        parsed = json.loads(raw_json)
        
        return OutreachResponse(
            job_id=job.id,
            subject_1=parsed.get("subject_1", f"{job.job_title} — Software Engineering experience"),
            subject_2=parsed.get("subject_2", f"Quick question re: {job.company_name}'s Engineering Team"),
            body=parsed.get("body", "Error generating body.")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Generation failed: {str(e)}")


@router.post("/ingest/file", response_model=JobIngestResponse)
async def ingest_jobs_from_file(
    file: UploadFile = File(...),
    bypass_filter: bool = Form(True),
    tailor_now: bool = Form(True),
    db: AsyncSession = Depends(get_db)
):
    """
    Ingest opportunities from uploaded PDF, CSV, or XLSX files.
    Runs extraction, deduplication, keyword pre-filter check, and queues LLM tailoring.
    """
    # 1. Validate file extension and MIME
    filename = file.filename or "uploaded_file"
    ext = filename.lower().split(".")[-1] if "." in filename else ""
    if ext not in ("pdf", "csv", "xlsx", "xls"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '.{ext}'. Supported formats are: .pdf, .csv, .xlsx."
        )

    # 2. Read file contents with 15MB limit
    max_size = 15 * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds maximum allowed limit of 15MB."
        )
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty."
        )

    # 3. Parse according to format
    try:
        if ext == "pdf":
            parsed_jobs = parse_pdf_bytes(content, filename=filename)
        elif ext == "csv":
            parsed_jobs = parse_csv_bytes(content, filename=filename)
        else:  # xlsx / xls
            parsed_jobs = parse_xlsx_bytes(content, filename=filename)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse {filename}: {str(e)}"
        )

    # 4. Execute ingestion and scoring pipeline
    response = await execute_job_ingest_pipeline(
        jobs_data=parsed_jobs,
        bypass_filter=bypass_filter,
        tailor_now=tailor_now,
        session=db
    )
    return response


@router.post("/ingest/urls", response_model=JobIngestResponse)
async def ingest_jobs_from_urls(
    payload: JobIngestUrlsRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Scrape and ingest job postings from links (Greenhouse, Lever, Ashby, Workable, LinkedIn, direct career pages).
    Applies SSRF protection, extracts content, and queues full tailoring engine.
    """
    if not payload.urls:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one URL must be provided."
        )

    parsed_jobs = []
    skipped_results = []

    for raw_url in payload.urls:
        url = raw_url.strip()
        if not url:
            continue
        try:
            job_data = await scrape_job_from_url(url)
            parsed_jobs.append(job_data)
        except Exception as e:
            skipped_results.append(IngestedJobItemResult(
                job_title="Unknown",
                company_name="Web Scraper",
                source_url=url,
                status="rejected",
                action_taken="error",
                error_message=f"Failed to scrape URL: {str(e)}"
            ))

    response = await execute_job_ingest_pipeline(
        jobs_data=parsed_jobs,
        bypass_filter=payload.bypass_filter,
        tailor_now=payload.tailor_now,
        session=db
    )

    # Merge any scrape errors
    response.results.extend(skipped_results)
    response.total_received += len(skipped_results)
    response.total_rejected += len(skipped_results)
    return response


@router.post("/ingest/text", response_model=JobIngestResponse)
async def ingest_jobs_from_text(
    payload: JobIngestTextRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Ingest job description from pasted raw text (single job or multiple jobs delimited by '---').
    Auto-detects title, company, stack via LLM or heuristics if omitted.
    """
    try:
        parsed_jobs = parse_raw_text_input(
            raw_text=payload.text,
            override_title=payload.job_title,
            override_company=payload.company_name,
            override_location=payload.location_raw,
            source_url=payload.source_url
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse job text: {str(e)}"
        )

    response = await execute_job_ingest_pipeline(
        jobs_data=parsed_jobs,
        bypass_filter=payload.bypass_filter,
        tailor_now=payload.tailor_now,
        session=db
    )
    return response

