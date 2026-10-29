"""Single personal-workspace profile API; every approval creates an immutable version."""
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db
from app.models import CandidateProfile, CandidateVersion, CandidateSource
from app.candidate_schemas import NoteRequest, AnalyzeRequest, DraftRequest, ApproveRequest
from app.services.candidate_profile import active_context, render_resume
from app.utils.pdf_generator import generate_resume_pdf, sanitize_filename
from app.workers.candidate_profile import process_candidate_source

router = APIRouter(prefix='/candidate', tags=['Candidate Profile'])


def source_response(source):
    return {key:getattr(source, key) for key in ('id','kind','title','status','raw_text','proposal','error','base_version_id','approved_version_id','created_at','updated_at')}


async def get_source(source_id, db):
    source = (await db.execute(select(CandidateSource).where(CandidateSource.id == source_id).with_for_update())).scalar_one_or_none()
    if not source:
        raise HTTPException(404, 'Source not found.')
    return source


async def queue(source, db):
    source.status = 'queued'
    source.error = None
    await db.commit()
    try:
        process_candidate_source.delay(str(source.id))
    except Exception:
        source.status = 'failed'
        source.error = 'Could not start background processing. Retry when the worker is available.'
        await db.commit()
    await db.refresh(source)
    return source_response(source)


@router.get('')
async def profile(db: AsyncSession = Depends(get_db)):
    context = await active_context(db)
    sources = (await db.execute(select(CandidateSource).order_by(CandidateSource.created_at.desc()).limit(100))).scalars().all()
    versions = (await db.execute(select(CandidateVersion).order_by(CandidateVersion.created_at.desc()).limit(30))).scalars().all()
    return {'version_id':context.version_id, 'profile':context.data, 'master_resume':context.resume,
            'sources':[source_response(s) for s in sources],
            'versions':[{'id':v.id,'name':v.data.get('name','Candidate'), 'created_at':v.created_at} for v in versions],
            'capabilities':{'extraction':bool(settings.effective_llm_key), 'voice':bool(settings.TRANSCRIPTION_API_KEY or settings.OPENAI_API_KEY)}}


@router.get('/identity')
async def identity(db: AsyncSession = Depends(get_db)):
    context = await active_context(db)
    return {'name':context.name, 'version_id':context.version_id}


@router.post('/notes', status_code=201)
async def notes(payload: NoteRequest, db: AsyncSession = Depends(get_db)):
    current = await active_context(db)
    source = CandidateSource(kind='project', title=payload.title.strip(), raw_text=payload.text.strip(), base_version_id=uuid.UUID(current.version_id))
    db.add(source)
    return await queue(source, db)


@router.post('/upload', status_code=201)
async def upload(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    suffix = Path(file.filename or '').suffix.lower()
    if suffix not in ('.pdf','.docx','.mp3','.mp4','.m4a','.wav','.webm','.ogg'):
        raise HTTPException(422, 'Upload a PDF/DOCX CV or an MP3, MP4, M4A, WAV, OGG, or WebM recording.')
    is_cv = suffix in ('.pdf','.docx')
    if not is_cv and not (settings.TRANSCRIPTION_API_KEY or settings.OPENAI_API_KEY):
        raise HTTPException(503, 'Voice transcription is not configured. You can still add project notes as text.')
    limit = (10 if is_cv else 20) * 1024 * 1024
    data = await file.read(limit + 1)
    if not data or len(data) > limit:
        raise HTTPException(413, f'Upload a nonempty file smaller than {limit // 1024 // 1024} MB.')
    if is_cv and not data.startswith(b'%PDF-' if suffix == '.pdf' else b'PK'):
        raise HTTPException(422, 'The file contents do not match the PDF/DOCX format.')
    current = await active_context(db)
    source_id = uuid.uuid4()
    folder = Path(settings.STORAGE_DIR) / 'candidate-sources'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (str(source_id) + suffix)
    path.write_bytes(data)
    source = CandidateSource(id=source_id, kind='resume' if is_cv else 'voice', title=Path(file.filename or 'Uploaded file').name[:300], file_path=str(path), base_version_id=uuid.UUID(current.version_id))
    db.add(source)
    try:
        return await queue(source, db)
    except Exception:
        path.unlink(missing_ok=True)
        raise


@router.get('/sources/{source_id}')
async def read_source(source_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return source_response(await get_source(source_id, db))


@router.post('/sources/{source_id}/analyze')
async def analyze(source_id: uuid.UUID, payload: AnalyzeRequest, db: AsyncSession = Depends(get_db)):
    source = await get_source(source_id, db)
    if source.status in ('queued','processing','approved'):
        raise HTTPException(409, 'This source is processing or already approved. Add a new note for further changes.')
    source.raw_text = payload.text.strip()
    source.base_version_id = uuid.UUID((await active_context(db)).version_id)
    source.proposal = None
    return await queue(source, db)


@router.put('/sources/{source_id}/draft')
async def save_draft(source_id: uuid.UUID, payload: DraftRequest, db: AsyncSession = Depends(get_db)):
    source = await get_source(source_id, db)
    if source.status != 'ready':
        raise HTTPException(409, 'Only a ready draft can be edited.')
    source.proposal = {**source.proposal, 'profile':payload.profile.model_dump()}
    await db.commit()
    return source_response(source)


@router.post('/sources/{source_id}/retry')
async def retry(source_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    source = await get_source(source_id, db)
    stale = source.updated_at < datetime.now(timezone.utc) - timedelta(minutes=10)
    if source.status != 'failed' and not (source.status in ('queued','processing') and stale):
        raise HTTPException(409, 'This source does not need a retry yet.')
    return await queue(source, db)


@router.post('/approve', status_code=201)
async def approve(payload: ApproveRequest, db: AsyncSession = Depends(get_db)):
    if not payload.profile.name.strip():
        raise HTTPException(422, 'Add the candidate’s name before approving.')
    root = (await db.execute(select(CandidateProfile).where(CandidateProfile.id == 1).with_for_update())).scalar_one()
    if root.active_version_id != payload.expected_version_id:
        raise HTTPException(409, 'The active profile changed. Reload it or re-analyze this source before approving.')
    source = await get_source(payload.source_id, db) if payload.source_id else None
    if source and (source.status != 'ready' or source.base_version_id != root.active_version_id):
        raise HTTPException(409, 'This draft is outdated or not ready. Re-analyze it against the current profile.')
    parent = await db.get(CandidateVersion, root.active_version_id)
    source_ids = list(parent.source_ids)
    if source and str(source.id) not in source_ids:
        source_ids.append(str(source.id))
    version = CandidateVersion(data=payload.profile.model_dump(), master_resume=payload.master_resume or render_resume(payload.profile.model_dump()), source_ids=source_ids)
    db.add(version)
    await db.flush()
    root.active_version_id = version.id
    if source:
        source.status = 'approved'
        source.approved_version_id = version.id
    await db.commit()
    return {'version_id':version.id, 'profile':version.data, 'master_resume':version.master_resume}


@router.get('/versions/{version_id}')
async def read_version(version_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    version = await db.get(CandidateVersion, version_id)
    if not version:
        raise HTTPException(404, 'Profile version not found.')
    return {'version_id':version.id, 'profile':version.data, 'master_resume':version.master_resume, 'source_ids':version.source_ids, 'created_at':version.created_at}


@router.get('/cv/pdf')
async def cv_pdf(db: AsyncSession = Depends(get_db)):
    context = await active_context(db)
    folder = Path(settings.STORAGE_DIR) / 'candidate-cvs' / context.version_id
    path = generate_resume_pdf(context.name, 'Master', '', context.resume, output_dir=str(folder))
    return FileResponse(path, media_type='application/pdf', filename=f'{sanitize_filename(context.name) or "Candidate"}_CV.pdf')
