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
from app.candidate_context import CANDIDATE_PROFILE, CANDIDATE_SYSTEM_PROMPT, CANDIDATE_BASE_RESUME
from app.utils.pdf_generator import generate_cover_letter_pdf, generate_resume_pdf

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
    def __init__(self):
        self.api_key = settings.effective_llm_key
        self.model = settings.effective_model
        base_url = settings.effective_base_url
        if self.api_key:
            if base_url:
                logger.info(f"Initializing LLM client with endpoint: {base_url} (Model: {self.model})")
                self.client = OpenAI(api_key=self.api_key, base_url=base_url, max_retries=0)
            else:
                self.client = OpenAI(api_key=self.api_key, max_retries=0)
        else:
            self.client = None

    def build_tailor_prompt(self, job_title: str, company_name: str, description: str) -> str:
        return f"""
Analyze the following job opportunity and tailor the application assets for Emmanuel Okeibunor.

Target Job:
Company: {company_name}
Title: {job_title}
Job Description:
{description}

STRICT INSTRUCTIONS:
Return a JSON object conforming strictly to this schema:
{{
  "match_score": integer (0 to 100),
  "match_reasoning": string,
  "tech_stack_tags": ["list", "of", "technologies"],
  "cover_letter_markdown": string (STRICTLY 250-400 words, 3-5 paragraphs. Para 1: Header, Greeting, and Hook referencing {company_name}. Para 2-3: Evidence & ATS keywords weaving Sycamore/ALN Riders achievements with metrics like 84% fraud reduction, 400k+ users. Para 4: Employer-centric value and proactive close. Do not use 'To Whom It May Concern'),
  "resume_markdown": string (ATS optimized resume tailoring the base resume to the job description. Use exact-match keywords, acronym expansion, reverse-chronological order, action-driven bullet points, and standard section headings),
  "ans_why_company_250": string (EXACTLY <= 250 characters),
  "ans_why_company_500": string (EXACTLY <= 500 characters),
  "ans_technical_challenge_250": string (EXACTLY <= 250 characters),
  "ans_technical_challenge_500": string (EXACTLY <= 500 characters),
  "ans_python_go_proficiency_220": string (EXACTLY <= 220 characters),
  "ans_location_relocation_220": string (EXACTLY <= 220 characters, Lagos, Nigeria location with remote & relocation readiness)
}}
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

    def generate_role_customized_cover_letter(
        self,
        job_title: str,
        company_name: str,
        description: str,
        archetype: str = "auto",
        custom_instructions: Optional[str] = None
    ) -> str:
        if archetype == "auto" or not archetype:
            archetype = self.detect_role_archetype(job_title, description)

        # 1. If LLM is available, craft a bespoke prompt honoring archetype + custom instructions
        if self.client:
            prompt = f"""
# Role & Objective
You are an expert career coach and technical copywriter. Your task is to generate tailored, high-converting, ATS-optimized cover letters for specific job applications based on the provided Candidate Profile, Job Description (JD), and Company Context.

Applying for: {job_title} at {company_name}
Role Archetype Focus: {archetype.upper()}
Custom Directives from Candidate: {custom_instructions or "None"}

# Candidate Ground Truth:
- Name: Emmanuel Okeibunor, based in Lagos, Nigeria (holds full readiness for global remote across time zones or full relocation).
- Portfolio: https://okeibunoremma.work | Email: okeibunoremma@gmail.com | Phone: +234 9015379412
- Sycamore Experience: Led frontend/software engineering for fraud detection & risk-management platform (84%+ fraud reduction). Scaled Nuxt applications to 400,000+ active users & 5,000+ daily logins. Architected core investment and B2B merchant banking products. Championed LLM-assisted coding workflows.
- ALN Riders Experience: Project Lead Engineer at ALN Riders (alnriders.com). Architected concurrent Golang backend services and Nuxt 4 frontends on Contabo Linux VPS, processing over $1M+ transaction value.
- E-nergie Experience: Built https://demo.e-nergie.co, appliance energy optimization platform with heuristic NILM power classification in Python and FastAPI.
- Pertinence & Numinix: Lead Frontend Developer on Oneapp (15k+ users) and built custom CI/CD pipelines.

# Formatting & Constraints
- **Length:** Strictly 250 to 400 words (3 to 5 concise paragraphs).
- **Tone:** Professional, confident, specific, and value-driven. Avoid generic fluff or overly AI-sounding buzzwords.

# Step-by-Step Structure
## 1. Header & Greeting
- Include standard business header with Name, City/Country, Phone, Email, Date, and Company Info.
- Greeting: "Dear Hiring Manager," (Never use "To Whom It May Concern").

## 2. Opening Paragraph (The Hook)
- State the exact job title being applied for.
- Express genuine interest by referencing a specific detail from the company (mission, product, etc.) and tie it directly to how your background contributes immediately.

## 3. Body Paragraphs (1-2 Paragraphs: Evidence & ATS Alignment)
- Select 2 to 3 core requirements from the Job Description.
- Show, Don't Just Tell: Weave your most recent and relevant achievements (Sycamore, ALN Riders, etc.) into a concise narrative demonstrating problem-solving.
- Quantify Impact: Back up claims with concrete metrics (e.g. 84%+ fraud reduction, 400k+ users, $1M+ transaction value).
- ATS Keyword Mirroring: Naturally integrate exact terminology and tools from the job description.

## 4. Closing Paragraph & Sign-off
- Employer-Centric Value: Summarize how your track record helps the team hit its goals.
- Call to Action & Gratitude: Thank the reader, reaffirm enthusiasm, and state you look forward to discussing how your experience aligns.
- Sign-off: "Sincerely,\\nEmmanuel Okeibunor".

# Strict Guardrails ("What to Avoid")
1. Never fabricate metrics or experience. Only use achievements present in the Candidate Profile.
2. Never focus solely on what the role does for the candidate—always frame enthusiasm around solving the employer's problems.
3. Never write walls of text. Keep paragraphs focused and scannable.

Return ONLY the raw markdown of the cover letter. Do not include placeholder brackets or markdown fences.
"""
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": CANDIDATE_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=600
                )
                text = resp.choices[0].message.content.strip()
                if len(text) > 200:
                    return text
            except Exception as e:
                logger.warning(f"LLM custom cover letter failed ({e}). Using archetype heuristic.")

        # 2. Archetype-Tailored Heuristic Cover Letter
        para1 = f"I am writing to express my strong enthusiasm for the {job_title} role at {company_name}. Your team's engineering mission and high-impact product focus deeply resonate with my drive to build scalable, resilient systems that deliver exceptional value to users."

        if archetype == "backend_systems":
            para2 = f"My technical depth is centered on concurrent backend architecture, high-throughput data processing, and reliable microservices. As Project Lead Engineer at ALN Riders (alnriders.com), I architected concurrent Golang backend services and asynchronous queues running on Contabo Linux infrastructure, processing over $1M+ in transaction volume. In addition, I created https://demo.e-nergie.co, an energy optimization platform utilizing Python and FastAPI with real-time heuristic signal parsing, PostgreSQL connection optimization, and Redis caching."
            para3 = f"At Sycamore, I engineered enterprise services supporting a mission-critical fraud detection rules engine that achieved an 84%+ fraud reduction while maintaining sub-100ms evaluation under concurrent user load. I architected core banking and investment products, scaling our backend and web applications to over 400,000 active users and 5,000 daily logins with zero downtime."
        elif archetype == "frontend_fullstack":
            para2 = f"My background bridges modern frontend excellence with full-stack capability. At Sycamore, I led frontend engineering for our consumer and B2B platforms, scaling Nuxt.js and TypeScript applications to over 400,000 active users and 5,000 daily logins. I engineered responsive merchant dashboards, architected complex investment products, and built our fraud management interface that eliminated latency bottlenecks for non-technical operations teams."
            para3 = f"Beyond UI layer craftsmanship, I take full ownership across the stack. I led development of ALN Riders (alnriders.com) using Nuxt 4 paired with concurrent Golang backend services, and architected https://demo.e-nergie.co using Python and FastAPI. I maintain a relentless focus on clean component architectures, robust state management, and intuitive user experiences."
        elif archetype == "devops_cloud":
            para2 = f"My background emphasizes reliable cloud infrastructure, containerization, and modern deployment automation. I have hands-on experience managing Contabo Linux VPS environments with Docker container orchestration, reverse proxy configurations, and automated CI/CD pipelines developed during my time with Numinix (Vancouver remote). I prioritize automated monitoring, network security, and infrastructure-as-code principles."
            para3 = f"At Sycamore, I maintained security-first engineering while supporting systems serving 400,000+ users. I engineered our enterprise fraud detection engine, achieving an 84%+ fraud reduction with strict RBAC access controls. Combined with high-throughput concurrent Golang backends at ALN Riders ($1M+ transaction value), I ensure services remain highly available and fault-tolerant."
        elif archetype == "ai_data":
            para2 = f"My engineering experience combines scalable systems with practical AI/ML data processing. I built https://demo.e-nergie.co, an appliance energy optimization platform in Python and FastAPI that implements heuristic Non-Intrusive Load Management (NILM) to classify real-time power signals. Furthermore, at Sycamore, I championed and established AI-assisted engineering and automated risk-triage workflows across our teams."
            para3 = f"I pair algorithmic problem solving with production scale. At Sycamore, I led software engineering for our fraud detection platform (84%+ fraud reduction across 400k+ active users), and at ALN Riders I architected concurrent Golang backend services handling $1M+ in transactions. I understand how to turn raw model outputs into reliable, low-latency production software."
        elif archetype == "leadership":
            para2 = f"As Project Lead Engineer at ALN Riders (alnriders.com), I owned the end-to-end technical roadmap, leading development of concurrent Golang backend APIs, Nuxt 4 web frontends, and cloud infrastructure on Contabo Linux VPS, surpassing $1M+ in transaction value across 500+ active customers. I thrive on translating ambiguous product requirements into high-velocity execution."
            para3 = f"At Sycamore, I led frontend engineering for our flagship fraud detection platform, delivering an 84%+ fraud reduction while scaling customer applications to 400,000+ active users. I actively mentor junior engineers, establish clear architectural patterns, and foster high engineering standards through pragmatic code and design reviews."
        else:
            para2 = f"My background combines modern frontend excellence with concurrent backend architecture. I built https://demo.e-nergie.co, an appliance energy optimization platform utilizing a heuristic Non-Intrusive Load Management (NILM) system in Python and FastAPI. Furthermore, as Project Lead Engineer at ALN Riders (alnriders.com), I architected concurrent Golang backend services and Nuxt 4 frontends on Contabo Linux infrastructure, processing over $1M+ in volume."
            para3 = f"At Sycamore, I led software engineering for an enterprise fraud detection and risk engine that drove an 84%+ fraud reduction, while scaling customer applications to over 400,000 active users and 5,000 daily logins. I architected core investment products, built internal banking tooling, and championed LLM-assisted workflows to accelerate development velocity."

        if custom_instructions and custom_instructions.strip():
            para3 += f"\n\nSpecifically regarding {company_name}'s focus: {custom_instructions.strip()}"

        para4 = f"Based in Lagos, Nigeria, I am fully equipped for remote work across global time zones and completely open to relocation. I thrive in collaborative, high-growth engineering cultures and look forward to contributing immediately to {company_name}."

        return f"{para1}\n\n{para2}\n\n{para3}\n\n{para4}"

    def _generate_heuristic_fallback(self, job_title: str, company_name: str, description: str) -> LLMTailorOutput:
        """Intelligent heuristic tailoring used as a reliable fallback when LLM is rate-limited or unavailable."""
        desc_lower = (job_title + " " + description).lower()
        
        # Analyze tech stack presence
        detected_tags = []
        stack_keywords = [
            ("Python", ["python", "fastapi", "django", "flask", "pydantic", "celery", "sqlalchemy"]),
            ("Go", ["golang", " go ", "goroutine", "grpc"]),
            ("TypeScript", ["typescript", "ts"]),
            ("Vue.js", ["vue", "vuejs", "vue 3", "vuex", "pinia"]),
            ("Nuxt", ["nuxt", "nuxt.js", "nuxt 3", "nuxt 4"]),
            ("React", ["react", "react.js", "next.js"]),
            ("PostgreSQL", ["postgres", "postgresql", "pgvector", "psql"]),
            ("Redis", ["redis", "caching", "in-memory"]),
            ("Docker", ["docker", "container", "containerization"]),
            ("Kubernetes", ["kubernetes", "k8s"]),
            ("AWS", ["aws", "amazon web services", "ec2", "s3"]),
            ("GCP", ["gcp", "google cloud"]),
            ("Linux", ["linux", "ubuntu", "systemd"]),
            ("Distributed Systems", ["distributed systems", "concurrency", "high availability", "microservices"]),
            ("REST API", ["rest api", "restful", "http api"])
        ]
        
        for tag, synonyms in stack_keywords:
            if any(syn in desc_lower for syn in synonyms):
                detected_tags.append(tag)
        
        # Determine match score based on technical relevance
        is_tech = any(w in desc_lower for w in ["software", "engineer", "developer", "backend", "frontend", "full stack", "fullstack", "platform", "infrastructure", "systems", "architect", "data", "security"])
        is_sales_or_non_eng = any(w in job_title.lower() for w in ["sales", "recruiter", "account executive", "legal", "hr ", "human resources", "people business"])
        
        if is_sales_or_non_eng:
            match_score = 42
            reasoning = "Role is non-technical / outside target domain of Full-Stack, Backend, and Systems Engineering."
        elif len(detected_tags) >= 3 or ("engineer" in desc_lower and "python" in desc_lower):
            match_score = 88
            reasoning = f"Strong alignment with core competencies in {', '.join(detected_tags[:4])}, concurrent backend systems, and modern full-stack architecture."
        elif is_tech:
            match_score = 78
            reasoning = f"Solid software engineering alignment matching {', '.join(detected_tags[:3]) if detected_tags else 'general software delivery'} and scalable service design."
        else:
            match_score = 55
            reasoning = "Moderate technical match; does not heavily leverage core Python, Go, or Nuxt stack."

        if not detected_tags:
            detected_tags = ["Python", "FastAPI", "TypeScript", "Docker"]

        archetype = self.detect_role_archetype(job_title, description)
        cover_letter = self.generate_role_customized_cover_letter(
            job_title=job_title,
            company_name=company_name,
            description=description,
            archetype=archetype
        )

        return LLMTailorOutput(
            match_score=match_score,
            match_reasoning=reasoning,
            tech_stack_tags=detected_tags,
            cover_letter_markdown=cover_letter,
            resume_markdown=CANDIDATE_BASE_RESUME,
            ans_why_company_250=clamp_text(f"{company_name}'s high-impact mission aligns with my passion for building scalable web apps with Nuxt, FastAPI, and Golang.", 250),
            ans_why_company_500=clamp_text(f"I admire {company_name}'s engineering focus. Having built platforms from fraud detection engines at Sycamore (400k+ users) to NILM energy analytics at e-nergie.co, I bring proven full-stack execution and ownership to your product roadmap.", 500),
            ans_technical_challenge_250=clamp_text("At Sycamore, I built an 84% fraud-reduction rules engine handling 400k+ users and sub-100ms evaluation without UI latency.", 250),
            ans_technical_challenge_500=clamp_text("Architected a non-intrusive load management system at e-nergie.co in FastAPI, solving real-time appliance power signal classification with heuristic algorithms, combined with concurrent Golang APIs at ALN Riders handling 1M+ transaction value.", 500),
            ans_python_go_proficiency_220=clamp_text("5+ years with Python (FastAPI/Django) building NILM systems & APIs. Proficient in Golang concurrency for high-throughput logistics backends.", 220),
            ans_location_relocation_220=clamp_text("Based in Lagos, Nigeria. Fully work-ready for global remote or full relocation to Europe, North America, and global tech hubs.", 220),
        )

    def generate_tailored_data(self, job_title: str, company_name: str, description: str) -> LLMTailorOutput:
        if not self.client:
            logger.warning("No LLM API key configured. Using heuristic fallback.")
            return self._generate_heuristic_fallback(job_title, company_name, description)

        system_prompt = f"{CANDIDATE_SYSTEM_PROMPT}\n\nBASE RESUME TO OPTIMIZE:\n{CANDIDATE_BASE_RESUME}"
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
                output = LLMTailorOutput.model_validate(parsed_data)
            except Exception as llm_err:
                logger.warning(f"LLM API completion failed ({llm_err}). Falling back to intelligent heuristic tailoring.")
                return self._generate_heuristic_fallback(job_title, company_name, description)

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

            # Score >= 65: Generate PDF and Assets
            job.status = JobStatus.READY_TO_APPLY

            pdf_path = generate_cover_letter_pdf(
                candidate_name=CANDIDATE_PROFILE["name"],
                company_name=job.company_name,
                job_title=job.job_title,
                cover_letter_markdown=tailored.cover_letter_markdown
            )
            
            resume_pdf_path_val = generate_resume_pdf(
                candidate_name=CANDIDATE_PROFILE["name"],
                company_name=job.company_name,
                job_title=job.job_title,
                resume_markdown=tailored.resume_markdown
            )

            # Insert or update application asset
            asset_stmt = select(ApplicationAsset).where(ApplicationAsset.job_id == job.id)
            asset_res = await session.execute(asset_stmt)
            asset = asset_res.scalar_one_or_none()

            if not asset:
                asset = ApplicationAsset(
                    job_id=job.id,
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
            else:
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
            logger.info(f"Successfully tailored & generated PDF for {job.job_title} at {job.company_name} (Score: {job.match_score})")


@celery_app.task(name="app.workers.llm_tailor.tailor_job_task")
def tailor_job_task(job_id_str: str) -> None:
    tailor = LLMTailor()
    asyncio.run(tailor.tailor_job(job_id_str))
