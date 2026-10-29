"""Real PostgreSQL/ASGI profile workflows with rollback and mocked providers."""
import os
import io
from zipfile import ZipFile
import tempfile
import unittest
import uuid
from contextlib import asynccontextmanager, ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import engine, get_db
from app.main import app
from app.config import settings
from app.models import CandidateSource, CandidateVersion, CandidateProfile, Job, ApplicationAsset, JobSource, JobStatus
from app.candidate_schemas import CandidateData
from app.workers.candidate_profile import process_source
from app.workers.llm_tailor import LLMTailor
from app.services.candidate_profile import CandidateContext, render_resume


@unittest.skipUnless(os.environ.get('RUN_DB_TESTS')=='1','Opt-in database integration tests')
class CandidateProfileDBTest(unittest.IsolatedAsyncioTestCase):
    async def test_draft_review_approval_versioning_application_isolation_and_pdf(self):
        key='candidate-test-'+uuid.uuid4().hex
        async with engine.connect() as connection:
            outer=await connection.begin()
            db=AsyncSession(bind=connection,expire_on_commit=False,join_transaction_mode='create_savepoint')
            async def dependency():yield db
            @asynccontextmanager
            async def factory():yield db
            app.dependency_overrides[get_db]=dependency
            try:
                with ExitStack() as stack, tempfile.TemporaryDirectory() as folder:
                    stack.enter_context(patch.object(settings,'STORAGE_DIR',folder))
                    for field in ('OPENAI_API_KEY','GEMINI_API_KEY','DEEPSEEK_API_KEY','TRANSCRIPTION_API_KEY'):
                        stack.enter_context(patch.object(settings,field,''))
                    stack.enter_context(patch('app.workers.candidate_profile.AsyncSessionLocal',factory))
                    stack.enter_context(patch('app.workers.llm_tailor.AsyncSessionLocal',factory))
                    enqueue=stack.enter_context(patch('app.api.candidate.process_candidate_source.delay'))
                    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
                        before=(await client.get('/api/candidate')).json()
                        initial=before['version_id']
                        created=await client.post('/api/candidate/notes',json={'title':key,'text':'I built a Rust sensor reader for tracking rainfall.'})
                        self.assertEqual(created.status_code,201,created.text)
                        source_id=created.json()['id']
                        enqueue.assert_called_once_with(source_id)
                        self.assertEqual((await client.get('/api/candidate')).json()['version_id'],initial)
                        await process_source(source_id)
                        source=(await client.get('/api/candidate/sources/'+source_id)).json()
                        self.assertEqual(source['status'],'ready',source)
                        draft=source['proposal']['profile']
                        draft['name']='Amina '+key;draft['location']='Nairobi';draft['skills']=['Rust']
                        saved=await client.put('/api/candidate/sources/'+source_id+'/draft',json={'profile':draft})
                        self.assertEqual(saved.status_code,200,saved.text)
                        approved=await client.post('/api/candidate/approve',json={'expected_version_id':initial,'source_id':source_id,'profile':draft})
                        self.assertEqual(approved.status_code,201,approved.text)
                        version=approved.json()['version_id']
                        self.assertNotEqual(version,initial)
                        stale=await client.post('/api/candidate/approve',json={'expected_version_id':initial,'profile':draft})
                        self.assertEqual(stale.status_code,409)
                        reused=await client.post('/api/candidate/approve',json={'expected_version_id':version,'source_id':source_id,'profile':draft})
                        self.assertEqual(reused.status_code,409)
                        # A rejected request leaves a transaction open; release it before further work.
                        await db.rollback()
                        # Savepoint rollback above doesn't undo previous successful approvals.
                        identity=(await client.get('/api/candidate/identity')).json()
                        self.assertEqual(identity['name'],'Amina '+key)
                        pdf=await client.get('/api/candidate/cv/pdf')
                        self.assertEqual(pdf.status_code,200,pdf.text[:100] if pdf.status_code!=200 else '')
                        self.assertTrue(pdf.content.startswith(b'%PDF-'))
                        job=Job(external_id=key,source=JobSource.MANUAL,source_url='https://example.org/'+key,company_name=key,job_title='Rust developer',description_raw='Build Rust tools for monitoring.',status=JobStatus.NEW)
                        db.add(job);await db.commit()
                        tailor=LLMTailor()
                        await tailor.tailor_job(str(job.id))
                        asset=(await db.execute(select(ApplicationAsset).where(ApplicationAsset.job_id==job.id))).scalar_one()
                        self.assertEqual(asset.candidate_snapshot['version_id'],version)
                        old_resume=asset.resume_markdown
                        changed={**draft,'name':'New '+key}
                        second=await client.post('/api/candidate/approve',json={'expected_version_id':version,'profile':changed})
                        self.assertEqual(second.status_code,201,second.text)
                        historical=(await client.get('/api/candidate/versions/'+version)).json()
                        self.assertEqual(historical['profile']['name'],'Amina '+key)
                        await db.refresh(asset)
                        self.assertEqual(asset.resume_markdown,old_resume)
                        self.assertEqual(asset.candidate_snapshot['data']['name'],'Amina '+key)
                        # Updating an old application still uses its original candidate snapshot.
                        letter=await client.post(f'/api/jobs/{job.id}/regenerate-cover-letter',json={})
                        self.assertEqual(letter.status_code,200,letter.text)
                        self.assertIn('Amina '+key,letter.json()['assets']['cover_letter_markdown'])
                        self.assertNotIn('New '+key,letter.json()['assets']['cover_letter_markdown'])
                        invalid=await client.post('/api/candidate/upload',files={'file':('bad.pdf',b'not a pdf','application/pdf')})
                        self.assertEqual(invalid.status_code,422)
                        voice=await client.post('/api/candidate/upload',files={'file':('voice.webm',b'audio','audio/webm')})
                        self.assertEqual(voice.status_code,503)
                        content=io.BytesIO()
                        with ZipFile(content,'w') as doc:
                            doc.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Amina Test, a Rust developer in Nairobi.</w:t></w:r></w:p></w:body></w:document>')
                        uploaded=await client.post('/api/candidate/upload',files={'file':('cv.docx',content.getvalue(),'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
                        self.assertEqual(uploaded.status_code,201,uploaded.text)
                        await process_source(uploaded.json()['id'])
                        extracted=(await client.get('/api/candidate/sources/'+uploaded.json()['id'])).json()
                        self.assertEqual(extracted['status'],'ready')
                        self.assertIn('Amina Test',extracted['raw_text'])
                        self.assertEqual(extracted['proposal']['profile']['name'],'')  # Manual review, never the previous identity.
                        enqueue.side_effect=RuntimeError('broker offline')
                        failed=await client.post('/api/candidate/notes',json={'title':key+' retry','text':'Project notes preserved when the task broker is offline.'})
                        self.assertEqual(failed.status_code,201,failed.text)
                        self.assertEqual(failed.json()['status'],'failed')
                        enqueue.side_effect=None
                        retried=await client.post('/api/candidate/sources/'+failed.json()['id']+'/retry')
                        self.assertEqual(retried.status_code,200,retried.text)
                        self.assertEqual(retried.json()['status'],'queued')
            finally:
                app.dependency_overrides.pop(get_db,None)
                await db.close();await outer.rollback()
        async with AsyncSession(engine) as verify:
            self.assertEqual((await verify.execute(select(Job).where(Job.company_name==key))).scalars().all(),[])

    async def test_voice_transcript_waits_for_review_before_extraction(self):
        async with engine.connect() as connection:
            outer=await connection.begin()
            db=AsyncSession(bind=connection,expire_on_commit=False,join_transaction_mode='create_savepoint')
            @asynccontextmanager
            async def factory():yield db
            try:
                current=(await db.execute(select(CandidateProfile.active_version_id).where(CandidateProfile.id==1))).scalar_one()
                with tempfile.TemporaryDirectory() as folder:
                    path=Path(folder)/'note.webm';path.write_bytes(b'mocked audio')
                    source=CandidateSource(kind='voice',title='Test recording',file_path=str(path),base_version_id=current)
                    db.add(source);await db.commit()
                    with patch('app.workers.candidate_profile.AsyncSessionLocal',factory),patch.object(settings,'TRANSCRIPTION_API_KEY','test'),patch('app.workers.candidate_profile.OpenAI') as client,patch('app.workers.candidate_profile.build_proposal') as extract:
                        client.return_value.audio.transcriptions.create.return_value=SimpleNamespace(text='I built a rainfall monitoring platform with Rust.')
                        await process_source(str(source.id))
                        extract.assert_not_called()
                    await db.refresh(source)
                    self.assertEqual(source.status,'transcribed')
                    self.assertIn('rainfall',source.raw_text)
                    self.assertIsNone(source.proposal)
                    # Duplicate task deliveries cannot repeat transcription.
                    with patch('app.workers.candidate_profile.AsyncSessionLocal',factory),patch('app.workers.candidate_profile.OpenAI') as client:
                        await process_source(str(source.id));client.assert_not_called()
            finally:
                await db.close();await outer.rollback()
