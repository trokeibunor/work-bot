import enum
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import (
    String, Text, Boolean, Integer, DateTime, ForeignKey, Index, func, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB, ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.database import Base


class JobStatus(str, enum.Enum):
    NEW = "new"
    QUEUED_FOR_LLM = "queued_for_llm"
    READY_TO_APPLY = "ready_to_apply"
    APPLIED = "applied"
    REJECTED = "rejected"
    INTERVIEW = "interview"
    ARCHIVED = "archived"


class JobSource(str, enum.Enum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    WORKABLE = "workable"
    REDDIT = "reddit"
    HACKERNEWS = "hackernews"


def get_enum_values(enum_cls):
    return [e.value for e in enum_cls]


class TargetCompany(Base):
    __tablename__ = "target_companies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ats_provider: Mapped[JobSource] = mapped_column(
        ENUM(JobSource, name="job_source", values_callable=get_enum_values, create_type=False), nullable=False
    )
    ats_slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_scraped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<TargetCompany {self.name} ({self.ats_provider}:{self.ats_slug})>"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[JobSource] = mapped_column(
        ENUM(JobSource, name="job_source", values_callable=get_enum_values, create_type=False), nullable=False
    )
    source_url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    company_name: Mapped[str] = mapped_column(Text, nullable=False)
    job_title: Mapped[str] = mapped_column(Text, nullable=False)
    location_raw: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_remote_or_relocation_friendly: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description_raw: Mapped[str] = mapped_column(Text, nullable=False)
    tech_stack_tags: Mapped[List[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    match_score: Mapped[int] = mapped_column(
        Integer,
        CheckConstraint("match_score >= 0 AND match_score <= 100", name="check_match_score_range"),
        default=0,
        nullable=False
    )
    match_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_founder_led: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        ENUM(JobStatus, name="job_status", values_callable=get_enum_values, create_type=False),
        default=JobStatus.NEW,
        nullable=False
    )
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(1536), nullable=True)

    assets: Mapped[Optional["ApplicationAsset"]] = relationship(
        "ApplicationAsset",
        back_populates="job",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    __table_args__ = (
        Index("idx_jobs_status_score", "status", match_score.desc()),
        Index("idx_jobs_created_at", created_at.desc()),
        Index("idx_jobs_source", "source"),
    )

    def __repr__(self) -> str:
        return f"<Job {self.job_title} at {self.company_name} ({self.status})>"


class ApplicationAsset(Base):
    __tablename__ = "application_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    cover_letter_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    cover_letter_pdf_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resume_markdown: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resume_pdf_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ans_why_company_250: Mapped[str] = mapped_column(String(250), nullable=False)
    ans_why_company_500: Mapped[str] = mapped_column(String(500), nullable=False)
    ans_technical_challenge_250: Mapped[str] = mapped_column(String(250), nullable=False)
    ans_technical_challenge_500: Mapped[str] = mapped_column(String(500), nullable=False)
    ans_python_go_proficiency_220: Mapped[str] = mapped_column(String(220), nullable=False)
    ans_location_relocation_220: Mapped[str] = mapped_column(String(220), nullable=False)
    custom_qa: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped["Job"] = relationship("Job", back_populates="assets")

    __table_args__ = (
        Index("idx_assets_job_id", "job_id"),
    )

    def __repr__(self) -> str:
        return f"<ApplicationAsset for Job {self.job_id}>"
