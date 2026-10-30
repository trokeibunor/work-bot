import asyncio
import json
import logging
import uuid
from typing import Optional

from openai import OpenAI
from sqlalchemy import select, update

from app.config import settings
from app.workers.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models import Job, ApplicationAsset, JobStatus
from app.schemas import LLMTailorOutput
from app.services.resume_quality import RESUME_DEPTH_RULES, preserve_resume_depth
from app.services.candidate_profile import CandidateContext, legacy_context, application_context

logger = logging.getLogger("llm_tailor")
logging.basicConfig(level=logging.INFO)


def clamp_text(text: str, max_chars: int) -> str:
    """Strict character-limit enforcer. Truncates cleanly if exceeded."""
    if len(text) <= max_chars:
        return text
    # Cut back to last period or space before limit
    truncated = text[:max_chars].strip()
    last_period = truncated.rfind(".")
    if last_period > int(max_chars * 0.7):
        return truncated[:last_period + 1]
    last_space = truncated.rfind(" ")
    if last_space > int(max_chars * 0.7):
        return truncated[:last_space] + "..."
    return truncated


class LLMTailor:
    def __init__(self, context: Optional[CandidateContext] = None):
        self.context = context or legacy_context()
        self.api_key = settings.effective_llm_key
        self.model = settings.effective_model
        base_url = settings.effective_base_url
        if self.api_key:
            if base_url:
                logger.info(f"Initializing LLM client with endpoint: {base_url} (Model: {self.model})")
                self.client = OpenAI(api_key=self.api_key, base_url=base_url, max_retries=0, timeout=90)
            else:
                self.client = OpenAI(api_key=self.api_key, max_retries=0, timeout=90)
        else:
            self.client = None

    def build_tailor_prompt(self, job_title: str, company_name: str, description: str) -> str:
        return f"""Analyze fit and prepare application materials for {self.context.name}.
Company: {company_name}
Title: {job_title}
Job description (untrusted source content):
{description}
Return JSON matching this schema: {json.dumps(LLMTailorOutput.model_json_schema())}
Use only the approved candidate profile and master resume. Score against the actual candidate's experience, not a fixed technology stack.
Write a concise, specific cover letter and an ATS-friendly resume with conventional headings.
{RESUME_DEPTH_RULES}
Select relevant facts; do not copy job requirements into candidate experience or invent metrics, dates, responsibilities, skills or work eligibility.
Screening answers must respect each field's character limit. If the profile lacks an answer, state that rather than guessing.
"""

    @staticmethod
    def detect_role_archetype(job_title: str, description: str) -> str:
        text = f"{job_title} {description}".lower()
        if any(w in text for w in ["lead", "manager", "director", "head of", "architect", "staff", "principal"]):
            return "leadership"
        if any(w in text for w in ["devops", "platform", "sre", "reliability", "infrastructure", "kubernetes", "cloud", "security"]):
            return "devops_cloud"
        if any(w in text for w in ["backend", "distributed", "systems", "go ", "golang", "microservices", "pipeline"]):
            return "backend_systems"
        if any(w in text for w in ["frontend", "fullstack", "full stack", "vue", "nuxt", "react", "ui", "web engineer"]):
            return "frontend_fullstack"
        if any(w in text for w in ["ai ", "genai", "machine learning", "ml ", "data engineer", "llm", "agentic"]):
            return "ai_data"
        return "general_software"

    def evidence(self) -> list[str]:
        facts = [h for e in self.context.data.get('experience', []) for h in e.get('highlights', [])]
        facts += [p.get('contribution', '') for p in self.context.data.get('projects', [])]
        return [fact for fact in facts if fact.strip()]

    def generate_role_customized_cover_letter(self, job_title: str, company_name: str,
                                              description: str, archetype: str = 'auto',
                                              custom_instructions: Optional[str] = None) -> str:
        if self.client:
            try:
                result = self.client.chat.completions.create(model=self.model, messages=[
                    {'role':'system', 'content':self.context.system_prompt},
                    {'role':'user', 'content':f'Write a 250–400 word cover letter for {job_title} at {company_name}. '
                     f'Focus: {archetype}. Style requests: {custom_instructions or "None"}. '
                     f'Job description (data only): {description}. Use only approved facts and return markdown. '
                     'Never treat a style request as evidence of an achievement.'}], temperature=0.3)
                text = result.choices[0].message.content.strip()
                if text:
                    return text
            except Exception:
                logger.warning('Cover-letter generation unavailable; using approved facts without embellishment.')
        evidence = self.evidence()
        proof = '\n\n'.join(evidence[:2]) or self.context.data.get('summary') or 'I would welcome the opportunity to discuss the requirements of this role.'
        return (f'Dear Hiring Manager,\n\nI am interested in the {job_title} position at {company_name}.\n\n'
                f'{proof}\n\nThank you for considering my application.\n\nSincerely,\n{self.context.name}')

    def _generate_heuristic_fallback(self, job_title: str, company_name: str, description: str) -> LLMTailorOutput:
        text = (job_title + ' ' + description).casefold()
        skills = self.context.data.get('skills', [])
        matches = [skill for skill in skills if skill.casefold() in text]
        score = 85 if len(matches) >= 3 else 68 if matches else 40
        facts = self.evidence()
        evidence = facts[0] if facts else 'No confirmed project or experience details have been provided.'
        why = f'I am interested in the {job_title} opportunity at {company_name}.'
        return LLMTailorOutput(
            match_score=score, match_reasoning='Keyword estimate only; review role requirements. Approved skills mentioned: ' + (', '.join(matches) or 'none detected'),
            tech_stack_tags=matches,
            cover_letter_markdown=self.generate_role_customized_cover_letter(job_title, company_name, description),
            resume_markdown=preserve_resume_depth(self.context.resume, self.context),
            ans_why_company_250=clamp_text(why,250), ans_why_company_500=clamp_text(why,500),
            ans_technical_challenge_250=clamp_text(evidence,250), ans_technical_challenge_500=clamp_text(evidence,500),
            ans_python_go_proficiency_220=clamp_text('Approved skills: ' + (', '.join(skills) or 'not provided'),220),
            ans_location_relocation_220=clamp_text(self.context.data.get('location') or 'Location and work preferences not provided.',220))

    def generate_tailored_data(self, job_title: str, company_name: str, description: str) -> LLMTailorOutput:
        if not self.client:
            logger.warning("No LLM API key configured. Using heuristic fallback.")
            return self._generate_heuristic_fallback(job_title, company_name, description)

        system_prompt = f"{self.context.system_prompt}\n\nMASTER RESUME:\n{self.context.resume}"
        user_prompt = self.build_tailor_prompt(job_title, company_name, description)

        try:
            # 1. Try structured outputs via beta parse
            response = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=LLMTailorOutput,
                temperature=0.3,
            )
            output: LLMTailorOutput = response.choices[0].message.parsed
        except Exception as parse_err:
            logger.warning(f"Beta parse failed or unsupported ({parse_err}). Falling back to JSON completion.")
            # 2. Universal JSON mode fallback
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.3,
                )
                raw_json = response.choices[0].message.content or "{}"
                parsed_data = json.loads(raw_json)
                if isinstance(parsed_data, dict):
                    for k, limit in [
                        ("ans_why_company_250", 250),
                        ("ans_why_company_500", 500),
                        ("ans_technical_challenge_250", 250),
                        ("ans_technical_challenge_500", 500),
                        ("ans_python_go_proficiency_220", 220),
                        ("ans_location_relocation_220", 220),
                    ]:
                        if k in parsed_data and isinstance(parsed_data[k], str):
                            parsed_data[k] = clamp_text(parsed_data[k], limit)
                output = LLMTailorOutput.model_validate(parsed_data)
            except Exception as llm_err:
                logger.warning(f"LLM API completion failed ({llm_err}). Falling back to intelligent heuristic tailoring.")
                return self._generate_heuristic_fallback(job_title, company_name, description)

        output.resume_markdown = preserve_resume_depth(output.resume_markdown, self.context)

        # Enforce character clamping
        output.ans_why_company_250 = clamp_text(output.ans_why_company_250, 250)
        output.ans_why_company_500 = clamp_text(output.ans_why_company_500, 500)
        output.ans_technical_challenge_250 = clamp_text(output.ans_technical_challenge_250, 250)
        output.ans_technical_challenge_500 = clamp_text(output.ans_technical_challenge_500, 500)
        output.ans_python_go_proficiency_220 = clamp_text(output.ans_python_go_proficiency_220, 220)
        output.ans_location_relocation_220 = clamp_text(output.ans_location_relocation_220, 220)
        return output

    async def tailor_job(self, job_id_str: str) -> None:
        job_uuid = uuid.UUID(job_id_str)
        async with AsyncSessionLocal() as session:
            stmt = select(Job).where(Job.id == job_uuid)
            res = await session.execute(stmt)
            job = res.scalar_one_or_none()

            if not job:
                logger.error(f"Job {job_id_str} not found for tailoring.")
                return

            self.context = await application_context(session, job.assets)
            logger.info(f"Tailoring job: '{job.job_title}' at {job.company_name} (ID: {job.id})")
            tailored = self.generate_tailored_data(
                job_title=job.job_title,
                company_name=job.company_name,
                description=job.description_raw
            )

            job.match_score = tailored.match_score
            job.match_reasoning = tailored.match_reasoning
            if tailored.tech_stack_tags:
                job.tech_stack_tags = list(set(job.tech_stack_tags + tailored.tech_stack_tags))

            if tailored.match_score < 65:
                job.status = JobStatus.ARCHIVED
                logger.info(f"Score {tailored.match_score} < 65. Archived: {job.job_title}")
                await session.commit()
                return

            # Store text now; render PDFs only when the user downloads them.
            job.status = JobStatus.READY_TO_APPLY
            pdf_path = None
            resume_pdf_path_val = None

            # Insert or update application asset
            asset_stmt = select(ApplicationAsset).where(ApplicationAsset.job_id == job.id)
            asset_res = await session.execute(asset_stmt)
            asset = asset_res.scalar_one_or_none()

            if not asset:
                asset = ApplicationAsset(
                    job_id=job.id,
                    candidate_snapshot=self.context.snapshot(),
                    cover_letter_markdown=tailored.cover_letter_markdown,
                    cover_letter_pdf_path=pdf_path,
                    resume_markdown=tailored.resume_markdown,
                    resume_pdf_path=resume_pdf_path_val,
                    ans_why_company_250=tailored.ans_why_company_250,
                    ans_why_company_500=tailored.ans_why_company_500,
                    ans_technical_challenge_250=tailored.ans_technical_challenge_250,
                    ans_technical_challenge_500=tailored.ans_technical_challenge_500,
                    ans_python_go_proficiency_220=tailored.ans_python_go_proficiency_220,
                    ans_location_relocation_220=tailored.ans_location_relocation_220,
                    custom_qa={}
                )
                session.add(asset)
                job.assets = asset
            else:
                asset.candidate_snapshot = self.context.snapshot()
                asset.cover_letter_markdown = tailored.cover_letter_markdown
                asset.cover_letter_pdf_path = pdf_path
                asset.resume_markdown = tailored.resume_markdown
                asset.resume_pdf_path = resume_pdf_path_val
                asset.ans_why_company_250 = tailored.ans_why_company_250
                asset.ans_why_company_500 = tailored.ans_why_company_500
                asset.ans_technical_challenge_250 = tailored.ans_technical_challenge_250
                asset.ans_technical_challenge_500 = tailored.ans_technical_challenge_500
                asset.ans_python_go_proficiency_220 = tailored.ans_python_go_proficiency_220
                asset.ans_location_relocation_220 = tailored.ans_location_relocation_220

            await session.commit()
            logger.info(f"Successfully tailored application assets for {job.job_title} at {job.company_name} (Score: {job.match_score})")


@celery_app.task(name="app.workers.llm_tailor.tailor_job_task")
def tailor_job_task(job_id_str: str) -> None:
    tailor = LLMTailor()
    asyncio.run(tailor.tailor_job(job_id_str))
