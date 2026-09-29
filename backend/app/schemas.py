import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.models import JobStatus, JobSource


# Asset Schemas
class ApplicationAssetBase(BaseModel):
    cover_letter_markdown: str
    cover_letter_pdf_path: Optional[str] = None
    resume_markdown: Optional[str] = None
    resume_pdf_path: Optional[str] = None
    ans_why_company_250: str = Field(..., max_length=250)
    ans_why_company_500: str = Field(..., max_length=500)
    ans_technical_challenge_250: str = Field(..., max_length=250)
    ans_technical_challenge_500: str = Field(..., max_length=500)
    ans_python_go_proficiency_220: str = Field(..., max_length=220)
    ans_location_relocation_220: str = Field(..., max_length=220)
    custom_qa: Dict[str, Any] = Field(default_factory=dict)


class ApplicationAssetResponse(ApplicationAssetBase):
    id: uuid.UUID
    job_id: uuid.UUID
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Job Schemas
class JobBase(BaseModel):
    external_id: str
    source: JobSource
    source_url: str
    company_name: str
    job_title: str
    location_raw: Optional[str] = None
    is_remote_or_relocation_friendly: bool = True
    description_raw: str
    tech_stack_tags: List[str] = Field(default_factory=list)
    match_score: int = Field(default=0, ge=0, le=100)
    match_reasoning: Optional[str] = None
    is_founder_led: bool = False
    status: JobStatus = JobStatus.NEW


class JobCreate(JobBase):
    pass


class JobResponse(JobBase):
    id: uuid.UUID
    applied_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HiringContactInfo(BaseModel):
    primary_email: str
    is_direct_listing_email: bool
    direct_emails: List[str] = Field(default_factory=list)
    derived_inboxes: List[str] = Field(default_factory=list)
    company_domain: str
    subject: str
    body: str
    mailto_url: str


class JobWithAssetResponse(JobResponse):
    assets: Optional[ApplicationAssetResponse] = None
    hiring_contacts: Optional[HiringContactInfo] = None

    model_config = ConfigDict(from_attributes=True)


class CoverLetterUpdateRequest(BaseModel):
    cover_letter_markdown: str = Field(..., min_length=50)


class CoverLetterRegenerateRequest(BaseModel):
    archetype: Optional[str] = Field(default="auto", description="Role archetype: 'auto', 'backend_systems', 'frontend_fullstack', 'devops_cloud', 'ai_data', 'leadership'")
    custom_instructions: Optional[str] = Field(default=None, description="Additional custom instructions")


class ResumeUpdateRequest(BaseModel):
    resume_markdown: str = Field(..., min_length=100)


class ResumeRegenerateRequest(BaseModel):
    custom_instructions: Optional[str] = Field(default=None, description="Additional custom instructions")


class PaginatedJobsResponse(BaseModel):
    items: List[JobWithAssetResponse]
    total: int
    page: int
    limit: int
    total_pages: int


class JobStatsResponse(BaseModel):
    ready_to_apply: int
    queued_for_llm: int
    applied: int
    archived: int
    founder_led: int = 0
    total: int


# Action Request / Response Schemas
class JobStatusUpdate(BaseModel):
    status: JobStatus


class CustomQuestionRequest(BaseModel):
    question: str = Field(..., min_length=3, description="The unexpected interview or application question")
    max_chars: int = Field(default=220, ge=50, le=2000, description="Strict character limit")


class CustomQuestionResponse(BaseModel):
    job_id: uuid.UUID
    question: str
    max_chars: int
    char_count: int
    answer: str


class OutreachRequest(BaseModel):
    recipient_persona: str = Field(default="technical_lead", description="Persona of the recipient: technical_lead, recruiter, founder")
    outreach_type: str = Field(default="post_application", description="Type of outreach: post_application, direct_pitch, follow_up")


class OutreachResponse(BaseModel):
    job_id: uuid.UUID
    subject_1: str
    subject_2: str
    body: str


class DailyMetricsResponse(BaseModel):
    today_applied: int
    daily_target: int
    remaining: int
    queued_ready: int
    weekly_streak: int


class ScrapeTriggerResponse(BaseModel):
    status: str
    message: str
    triggered_at: datetime = Field(default_factory=datetime.utcnow)


# LLM Structured Output Schema
class LLMTailorOutput(BaseModel):
    match_score: int = Field(..., ge=0, le=100, description="Fit score from 0 to 100 based on candidate experience and stack")
    match_reasoning: str = Field(..., description="Concise rationale explaining the score")
    tech_stack_tags: List[str] = Field(default_factory=list, description="Technologies detected in the job")
    cover_letter_markdown: str = Field(..., description="Tailored 4-paragraph cover letter strictly following guidelines")
    resume_markdown: str = Field(..., description="Tailored ATS-friendly markdown resume mirroring keywords from job description")
    ans_why_company_250: str = Field(..., max_length=250, description="Strictly <= 250 characters answer to why this company")
    ans_why_company_500: str = Field(..., max_length=500, description="Strictly <= 500 characters answer to why this company")
    ans_technical_challenge_250: str = Field(..., max_length=250, description="Strictly <= 250 characters technical challenge answer")
    ans_technical_challenge_500: str = Field(..., max_length=500, description="Strictly <= 500 characters technical challenge answer")
    ans_python_go_proficiency_220: str = Field(..., max_length=220, description="Strictly <= 220 characters Python and Go proficiency summary")
    ans_location_relocation_220: str = Field(..., max_length=220, description="Strictly <= 220 characters Lagos, Nigeria location & relocation readiness")
