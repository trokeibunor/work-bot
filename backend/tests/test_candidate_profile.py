import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile

from app.candidate_schemas import CandidateData, Project, Extraction
from app.services.candidate_profile import CandidateContext, render_resume
from app.workers.candidate_profile import extract_cv, build_proposal
from app.workers.llm_tailor import LLMTailor
from app.utils.pdf_generator import generate_resume_pdf, generate_cover_letter_pdf
from app.config import settings


class CandidateProfileTest(unittest.TestCase):
    def profile(self):
        return CandidateData(name='Amina Test', location='Nairobi', skills=['Rust'],
                             projects=[Project(name='Water monitor', contribution='Built a Rust sensor reader.')]).model_dump()

    def no_provider(self):
        from contextlib import ExitStack
        stack = ExitStack()
        for field in ('OPENAI_API_KEY','GEMINI_API_KEY','DEEPSEEK_API_KEY'):
            stack.enter_context(patch.object(settings,field,''))
        return stack

    def test_renderer_uses_actual_profile_and_preserves_metrics(self):
        profile = self.profile()
        profile['projects'][0]['outcomes']=['Reduced delays by 12%; cost was KES 4,000.']
        resume = render_resume(profile)
        self.assertIn('Amina Test',resume)
        self.assertIn('KES 4,000',resume)
        self.assertNotIn('Sycamore',resume)
        self.assertNotIn('Emmanuel',resume)

    def test_project_fallback_preserves_note_and_does_not_infer_metrics(self):
        with self.no_provider():
            result = build_proposal('I built a rainfall monitor using a Rust sensor reader.','project','Rainfall',self.profile())
        self.assertEqual(result['profile']['name'],'Amina Test')
        self.assertEqual(result['profile']['projects'][-1]['outcomes'],[])
        self.assertEqual(result['profile']['projects'][-1]['contribution'],'I built a rainfall monitor using a Rust sensor reader.')
        self.assertTrue(result['questions'])

    def test_cv_fallback_does_not_mix_previous_candidate_into_new_cv(self):
        with self.no_provider():
            result = build_proposal('Another person with a completely different background.','resume','New CV',self.profile())
        self.assertEqual(result['profile']['name'],'')
        self.assertEqual(result['profile']['projects'],[])
        self.assertTrue(result['warnings'])

    def test_ai_project_proposal_cannot_replace_identity_or_employment(self):
        extracted = Extraction(profile=CandidateData(name='Wrong identity', skills=['Invented skill'], projects=[Project(name='Rainfall',role='Developer',contribution='Built a reader.')]))
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=extracted.model_dump_json()))])
        with patch.object(settings,'OPENAI_API_KEY','test'), patch('app.workers.candidate_profile.OpenAI') as client:
            client.return_value.chat.completions.create.return_value=response
            result=build_proposal('I built a reader for rainfall sensors.','project','Rainfall',self.profile())
        self.assertEqual(result['profile']['name'],'Amina Test')
        self.assertEqual(result['profile']['skills'],['Rust'])
        self.assertEqual(len(result['profile']['projects']),2)

    def test_replacing_cv_reports_identity_conflicts_and_missing_fields(self):
        extracted=Extraction(profile=CandidateData(name='Different Candidate', location='Accra'))
        response=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=extracted.model_dump_json()))])
        with patch.object(settings,'OPENAI_API_KEY','test'),patch('app.workers.candidate_profile.OpenAI') as client:
            client.return_value.chat.completions.create.return_value=response
            result=build_proposal('Different Candidate, Accra.','resume','CV',self.profile())
        self.assertTrue(any('Name differs' in w for w in result['warnings']))
        self.assertEqual(result['profile']['projects'],[])

    def test_docx_extraction_and_invalid_input(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'cv.docx'
            with ZipFile(path,'w') as doc:
                doc.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Amina Test, a Rust engineer in Nairobi.</w:t></w:r></w:p></w:body></w:document>')
            self.assertEqual(extract_cv(str(path)),'Amina Test, a Rust engineer in Nairobi.')
            path.write_bytes(b'not a document')
            with self.assertRaises(ValueError):extract_cv(str(path))

    def test_pdfs_support_candidate_identity_and_special_characters(self):
        from pypdf import PdfReader
        with tempfile.TemporaryDirectory() as folder:
            path=generate_resume_pdf('Amina Test','Master','', '# Amina Test\n## Projects\n- Built R&D tools for <sensors>.',folder)
            self.assertTrue(Path(path).name.startswith('Amina_Test'))
            self.assertIn('Amina Test',PdfReader(path).pages[0].extract_text())
            letter=generate_cover_letter_pdf('Amina Test','R&D <Lab>','Engineer','Hello, **I built R&D tools**.\n\nSincerely,\nAmina Test',folder,{'email':'amina@example.org'})
            text='\n'.join(p.extract_text() for p in PdfReader(letter).pages)
            self.assertIn('amina@example.org',text)
            self.assertNotIn('Emmanuel',text)

    def test_generation_fallback_uses_only_this_candidate(self):
        with self.no_provider():
            tailor=LLMTailor(CandidateContext(self.profile(),render_resume(self.profile()),'test-version'))
            result=tailor.generate_tailored_data('Rust developer','Sensor Org','Build Rust monitoring tools.')
        data=result.model_dump_json()
        self.assertIn('Amina Test',data)
        self.assertIn('Nairobi',data)
        for forbidden in ('Emmanuel','Sycamore','ALN Riders','400,000','Lagos','84%'):
            self.assertNotIn(forbidden,data)
        self.assertEqual(result.tech_stack_tags,['Rust'])

    def test_legacy_profile_retains_separate_dated_pertinence_and_numinix(self):
        from app.services.candidate_profile import legacy_context
        context=legacy_context()
        roles={e['company']:e for e in context.data['experience']}
        self.assertEqual(roles['Pertinence Group']['period'],'03/2023 - 10/2024')
        self.assertEqual(roles['Pertinence Group']['role'],'Lead Frontend Developer')
        self.assertGreaterEqual(len(roles['Pertinence Group']['highlights']),3)
        self.assertEqual(roles['Numinix Web Technologies']['period'],'11/2024 - 03/2025')
        self.assertNotIn('Prior Experience',context.resume)

    def test_optimization_rejects_omitted_early_roles_and_reduced_achievements(self):
        from app.services.candidate_profile import legacy_context
        from app.services.resume_quality import preserve_resume_depth, coverage_issues
        context=legacy_context()
        shortened='# Emmanuel Okeibunor\n## Work Experience\nSycamore, Software Engineer, 02/2025 - Present\n- Built applications.'
        self.assertTrue(coverage_issues(shortened,context))
        restored=preserve_resume_depth(shortened,context)
        self.assertIn('Pertinence Group',restored)
        self.assertIn('03/2023 - 10/2024',restored)
        self.assertIn('Repository Pattern',restored)
        self.assertIn('15,000',restored)
        self.assertFalse(coverage_issues(restored,context))

    def test_complete_tailored_resume_is_preserved_without_shortening(self):
        from app.services.candidate_profile import legacy_context
        from app.services.resume_quality import preserve_resume_depth
        context=legacy_context()
        tailored=context.resume.replace('## Skills','## Technical Skills')
        self.assertEqual(preserve_resume_depth(tailored,context),tailored)

    def test_regeneration_can_use_approved_repair_of_condensed_legacy_snapshot(self):
        import asyncio
        from unittest.mock import AsyncMock
        from app.services.candidate_profile import legacy_context, application_context
        repaired=legacy_context()
        repaired.version_id='repaired-version'
        old=self.profile()
        old['name']=repaired.name
        old['experience']=[{'company':'Numinix & Pertinence Group','role':'Software Engineer / Lead Frontend Developer','period':'Prior Experience','highlights':[]}]
        asset=SimpleNamespace(candidate_snapshot={'data':old,'resume':'Old condensed CV','version_id':'old-version'})
        with patch('app.services.candidate_profile.active_context',new=AsyncMock(return_value=repaired)):
            result=asyncio.run(application_context(None,asset))
        self.assertEqual(result.version_id,'repaired-version')
        self.assertIn('03/2023 - 10/2024',result.resume)
        self.assertEqual(asset.candidate_snapshot['resume'],'Old condensed CV')
