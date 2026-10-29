"""Opt-in PostgreSQL/API checks. All fixture writes roll back; no AI tasks run.
Run with RUN_DB_TESTS=1 against an initialized local database.
"""
import os
import unittest
import uuid
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import engine, get_db
from app.main import app
from app.models import Job, JobSource, JobStatus
from app.utils.job_parser import execute_job_ingest_pipeline


@unittest.skipUnless(os.environ.get('RUN_DB_TESTS') == '1', 'Opt-in database integration test')
class JobWorkflowDBTest(unittest.IsolatedAsyncioTestCase):
    async def test_filter_bulk_undo_apply_and_prepare_with_real_database(self):
        key = 'workflow-' + uuid.uuid4().hex
        async with engine.connect() as connection:
            outer = await connection.begin()
            db = AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode='create_savepoint')
            async def dependency():
                yield db
            app.dependency_overrides[get_db] = dependency
            try:
                fixtures = []
                for i, (status, description) in enumerate([
                    (JobStatus.READY_TO_APPLY, 'We are a non-profit organization hiring an engineer.'),
                    (JobStatus.NEW, 'We build tools for an NGO.'),
                    (JobStatus.APPLIED, 'An ordinary engineering role.'),
                ]):
                    job = Job(external_id=f'{key}-{i}', source=JobSource.MANUAL,
                              source_url=f'https://example.org/{key}/{i}', company_name=key,
                              job_title='Engineer', description_raw=description,
                              status=status, match_score=80)
                    db.add(job)
                    fixtures.append(job)
                await db.commit()
                ids = [str(job.id) for job in fixtures]
                async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
                    response = await client.get('/api/jobs', params={'search':key, 'organization_type':'nonprofit'})
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(response.json()['total'], 2)
                    self.assertTrue(all(item['organization_type']=='nonprofit' for item in response.json()['items']))
                    invalid = await client.get('/api/jobs', params={'organization_type':'anything'})
                    self.assertEqual(invalid.status_code, 422)
                    ignored = await client.post('/api/jobs/bulk', json={'action':'ignore','job_ids':ids})
                    self.assertEqual(ignored.status_code, 200, ignored.text)
                    self.assertEqual(len(ignored.json()['updated_ids']), 2)
                    self.assertEqual(len(ignored.json()['skipped']), 1)
                    undone = await client.post('/api/jobs/bulk', json={'action':'restore','job_ids':ids[:2], 'previous_statuses':ignored.json()['previous_statuses']})
                    self.assertEqual(len(undone.json()['updated_ids']), 2)
                    applied = await client.post('/api/jobs/bulk', json={'action':'mark_applied','job_ids':ids})
                    self.assertEqual(applied.json()['updated_ids'], ids[:1])
                    with patch('app.workers.llm_tailor.tailor_job_task.delay') as enqueue:
                        prepared = await client.post('/api/jobs/bulk', json={'action':'prepare','job_ids':ids})
                    self.assertEqual(prepared.json()['updated_ids'], ids[1:2])
                    enqueue.assert_called_once_with(ids[1])
                    result = await client.get('/api/jobs/' + ids[1])
                    self.assertEqual(result.json()['status'], 'queued_for_llm')
                    # The generated classification updates automatically on edits.
                    fixtures[1].description_raw = 'Generic engineering vacancy.'
                    await db.commit()
                    response = await client.get('/api/jobs', params={'search':key, 'organization_type':'nonprofit'})
                    self.assertEqual(response.json()['total'], 1)
                    # Imports saved for later remain eligible for bulk preparation.
                    with patch('app.utils.job_parser.tailor_job_task.delay') as enqueue:
                        saved = await execute_job_ingest_pipeline([{
                            'job_title':'Engineer', 'company_name':key,
                            'description_raw':'An engineering role saved for later.',
                            'source_url':f'https://example.org/{key}/saved',
                        }], bypass_filter=True, tailor_now=False, session=db)
                    enqueue.assert_not_called()
                    self.assertEqual(saved.total_queued, 0)
                    self.assertEqual(saved.results[0].status, 'new')
                    self.assertEqual(saved.results[0].action_taken, 'saved')
                    with patch('app.utils.job_parser.tailor_job_task.delay', side_effect=RuntimeError('broker offline')):
                        retry = await execute_job_ingest_pipeline([{
                            'job_title':'Engineer', 'company_name':key,
                            'description_raw':'A role with a failed preparation dispatch.',
                            'source_url':f'https://example.org/{key}/retry',
                        }], bypass_filter=True, tailor_now=True, session=db)
                    self.assertEqual(retry.total_queued, 0)
                    self.assertEqual(retry.results[0].status, 'new')
            finally:
                app.dependency_overrides.pop(get_db, None)
                await db.close()
                await outer.rollback()
        async with AsyncSession(engine) as verify:
            self.assertEqual((await verify.execute(select(Job).where(Job.company_name == key))).scalars().all(), [])
