import os
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Job, ApplicationAsset
from app.config import settings
from app.candidate_context import CANDIDATE_PROFILE
from app.utils.pdf_generator import generate_cover_letter_pdf, generate_resume_pdf, sanitize_filename

router = APIRouter(prefix="/assets", tags=["Assets"])


@router.get("/{job_id}/pdf")
async def get_cover_letter_pdf(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    # Fetch job and asset
    stmt = select(Job).where(Job.id == job_id)
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found."
        )

    asset_stmt = select(ApplicationAsset).where(ApplicationAsset.job_id == job_id)
    asset_res = await db.execute(asset_stmt)
    asset = asset_res.scalar_one_or_none()
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No application assets generated for job {job_id} yet."
        )

    pdf_path = asset.cover_letter_pdf_path
    if not pdf_path or not os.path.exists(pdf_path):
        # Generate on the fly if file is missing
        pdf_path = generate_cover_letter_pdf(
            candidate_name=CANDIDATE_PROFILE["name"],
            company_name=job.company_name,
            job_title=job.job_title,
            cover_letter_markdown=asset.cover_letter_markdown
        )
        asset.cover_letter_pdf_path = pdf_path
        await db.commit()

    # Path traversal security check
    real_path = Path(pdf_path).resolve()
    base_storage = Path(settings.STORAGE_DIR).resolve()
    if not str(real_path).startswith(str(base_storage)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to specified file path is denied."
        )

    company_slug = sanitize_filename(job.company_name)
    download_filename = f"Emmanuel_Okeibunor_Cover_Letter_{company_slug}.pdf"

    return FileResponse(
        path=str(real_path),
        media_type="application/pdf",
        filename=download_filename,
        headers={"Content-Disposition": f'inline; filename="{download_filename}"'}
    )


@router.get("/{job_id}/resume/pdf")
async def get_resume_pdf(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    # Fetch job and asset
    stmt = select(Job).where(Job.id == job_id)
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found."
        )

    asset_stmt = select(ApplicationAsset).where(ApplicationAsset.job_id == job_id)
    asset_res = await db.execute(asset_stmt)
    asset = asset_res.scalar_one_or_none()
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No application assets generated for job {job_id} yet."
        )

    if not asset.resume_markdown:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume not generated for job {job_id} yet."
        )

    pdf_path = asset.resume_pdf_path
    if not pdf_path or not os.path.exists(pdf_path):
        # Generate on the fly if file is missing
        pdf_path = generate_resume_pdf(
            candidate_name=CANDIDATE_PROFILE["name"],
            company_name=job.company_name,
            job_title=job.job_title,
            resume_markdown=asset.resume_markdown
        )
        asset.resume_pdf_path = pdf_path
        await db.commit()

    # Path traversal security check
    real_path = Path(pdf_path).resolve()
    base_storage = Path(settings.STORAGE_DIR).resolve()
    if not str(real_path).startswith(str(base_storage)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to specified file path is denied."
        )

    company_slug = sanitize_filename(job.company_name)
    download_filename = f"Emmanuel_Okeibunor_Resume_{company_slug}.pdf"

    return FileResponse(
        path=str(real_path),
        media_type="application/pdf",
        filename=download_filename,
        headers={"Content-Disposition": f'inline; filename="{download_filename}"'}
    )
