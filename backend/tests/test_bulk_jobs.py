"""Bulk operations must preserve submitted work and report partial failures."""
import uuid
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.api.jobs import bulk_jobs
from app.models import JobStatus
from app.schemas import BulkJobRequest


class BulkJobsTest(unittest.IsolatedAsyncioTestCase):
    def job(self, status):
        return SimpleNamespace(id=uuid.uuid4(), status=status, applied_at=None)

    def db(self, jobs):
        return SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: jobs))), commit=AsyncMock())

    async def test_ignore_deduplicates_and_preserves_submitted_and_preparing(self):
        ready, applied, queued = [self.job(s) for s in [JobStatus.READY_TO_APPLY, JobStatus.APPLIED, JobStatus.QUEUED_FOR_LLM]]
        missing = uuid.uuid4()
        db = self.db([ready, applied, queued])
        result = await bulk_jobs(BulkJobRequest(action='ignore', job_ids=[ready.id, ready.id, applied.id, queued.id, missing]), db)
        self.assertEqual(result['updated_ids'], [str(ready.id)])
        self.assertEqual(result['previous_statuses'], {str(ready.id): 'ready_to_apply'})
        self.assertEqual(len(result['skipped']), 3)
        self.assertEqual(applied.status, JobStatus.APPLIED)
        self.assertEqual(queued.status, JobStatus.QUEUED_FOR_LLM)
        self.assertEqual(ready.status, JobStatus.ARCHIVED)

    async def test_undo_restores_previous_status_and_skips_changed_job(self):
        ignored, changed = self.job(JobStatus.ARCHIVED), self.job(JobStatus.APPLIED)
        result = await bulk_jobs(BulkJobRequest(action='restore', job_ids=[ignored.id, changed.id], previous_statuses={ignored.id: 'new', changed.id: 'ready_to_apply'}), self.db([ignored, changed]))
        self.assertEqual(ignored.status, JobStatus.NEW)
        self.assertEqual(changed.status, JobStatus.APPLIED)
        self.assertEqual(len(result['skipped']), 1)

    async def test_mark_applied_only_updates_ready_roles_once(self):
        ready, new = self.job(JobStatus.READY_TO_APPLY), self.job(JobStatus.NEW)
        result = await bulk_jobs(BulkJobRequest(action='mark_applied', job_ids=[ready.id,new.id]), self.db([ready,new]))
        self.assertEqual(ready.status, JobStatus.APPLIED)
        self.assertIsNotNone(ready.applied_at)
        self.assertEqual(new.status, JobStatus.NEW)
        self.assertEqual(len(result['updated_ids']), 1)
        again = await bulk_jobs(BulkJobRequest(action='mark_applied', job_ids=[ready.id]), self.db([ready]))
        self.assertEqual(again['updated_ids'], [])

    async def test_prepare_reports_broker_failure_and_releases_reservation(self):
        first, second, ready = self.job(JobStatus.NEW), self.job(JobStatus.NEW), self.job(JobStatus.READY_TO_APPLY)
        db = self.db([first, second, ready])
        with patch('app.workers.llm_tailor.tailor_job_task.delay', side_effect=[None, RuntimeError('broker offline')]) as enqueue:
            result = await bulk_jobs(BulkJobRequest(action='prepare', job_ids=[first.id,second.id,ready.id]), db)
        self.assertEqual(enqueue.call_count, 2)
        self.assertEqual(result['updated_ids'], [str(first.id)])
        self.assertEqual(len(result['skipped']), 2)
        self.assertEqual(db.execute.await_count, 2)  # Includes reservation rollback.
        self.assertEqual(ready.status, JobStatus.READY_TO_APPLY)

    def test_batch_size_is_bounded(self):
        from pydantic import ValidationError
        for ids in [[], [uuid.uuid4() for _ in range(101)]]:
            with self.assertRaises(ValidationError):
                BulkJobRequest(action='ignore', job_ids=ids)
