"""Exercise lazy PDF generation without a live database or LLM provider."""
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.api import assets
from app.api.jobs import update_cover_letter, update_resume
from app.schemas import CoverLetterUpdateRequest, ResumeUpdateRequest


class PDFDownloadsTest(unittest.IsolatedAsyncioTestCase):
    def session(self, job, asset):
        db = SimpleNamespace(execute=AsyncMock(), commit=AsyncMock(), refresh=AsyncMock())
        db.execute.side_effect = [
            SimpleNamespace(scalar_one_or_none=lambda: job),
            SimpleNamespace(scalar_one_or_none=lambda: asset),
        ]
        return db

    def job_and_asset(self):
        job = SimpleNamespace(id=uuid.uuid4(), company_name='Same Company', job_title='Engineer')
        asset = SimpleNamespace(cover_letter_pdf_path=None, resume_pdf_path=None,
                                cover_letter_markdown='A tailored cover letter.',
                                resume_markdown='A tailored resume.')
        return job, asset

    async def test_downloads_generate_valid_pdfs_and_reuse_cache(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(assets.settings, 'STORAGE_DIR', folder):
            for endpoint, field in [(assets.get_cover_letter_pdf, 'cover_letter_pdf_path'),
                                    (assets.get_resume_pdf, 'resume_pdf_path')]:
                job, asset = self.job_and_asset()
                db = self.session(job, asset)
                response = await endpoint(job.id, db)
                path = Path(response.path)
                self.assertTrue(path.read_bytes().startswith(b'%PDF-'))
                self.assertEqual(path.parent, (Path(folder) / str(job.id)).resolve())
                self.assertEqual(Path(getattr(asset, field)).resolve(), path)
                db.commit.assert_awaited_once()
                db = self.session(job, asset)
                await endpoint(job.id, db)
                db.commit.assert_not_awaited()

    async def test_same_company_jobs_have_separate_files(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(assets.settings, 'STORAGE_DIR', folder):
            paths = []
            for _ in range(2):
                job, asset = self.job_and_asset()
                response = await assets.get_cover_letter_pdf(job.id, self.session(job, asset))
                paths.append(response.path)
            self.assertNotEqual(*paths)
            self.assertTrue(all(Path(path).exists() for path in paths))

    async def test_legacy_shared_file_is_replaced_with_job_scoped_file(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(assets.settings, 'STORAGE_DIR', folder):
            job, asset = self.job_and_asset()
            old_path = Path(folder) / 'shared.pdf'
            old_path.write_bytes(b'legacy')
            asset.cover_letter_pdf_path = str(old_path)
            response = await assets.get_cover_letter_pdf(job.id, self.session(job, asset))
            self.assertNotEqual(response.path, str(old_path))
            self.assertEqual(old_path.read_bytes(), b'legacy')

    async def test_edits_invalidate_pdf_without_rendering(self):
        for endpoint, payload, text_field, path_field in [
            (update_cover_letter, CoverLetterUpdateRequest(cover_letter_markdown='Updated cover letter. ' * 5),
             'cover_letter_markdown', 'cover_letter_pdf_path'),
            (update_resume, ResumeUpdateRequest(resume_markdown='Updated resume experience. ' * 8),
             'resume_markdown', 'resume_pdf_path'),
        ]:
            job, asset = self.job_and_asset()
            job.assets = asset
            setattr(asset, path_field, '/old/cached.pdf')
            db = self.session(job, asset)
            with patch('app.api.jobs.build_job_with_asset_response', return_value=job):
                await endpoint(job.id, payload, db)
            self.assertEqual(getattr(asset, text_field), getattr(payload, text_field))
            self.assertIsNone(getattr(asset, path_field))
            db.commit.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
