"""Validated facts shared by extraction, review, and application generation."""
import uuid
from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


class Contact(BaseModel):
    email: str = Field(default='', max_length=320)
    phone: str = Field(default='', max_length=100)
    portfolio: str = Field(default='', max_length=500)
    linkedin: str = Field(default='', max_length=500)
    github: str = Field(default='', max_length=500)


class Experience(BaseModel):
    company: str = Field(default='', max_length=300)
    role: str = Field(default='', max_length=300)
    period: str = Field(default='', max_length=150)
    highlights: list[str] = Field(default_factory=list, max_length=30)


class Education(BaseModel):
    degree: str = Field(default='', max_length=500)
    institution: str = Field(default='', max_length=500)
    period: str = Field(default='', max_length=150)


class Project(BaseModel):
    name: str = Field(default='', max_length=300)
    role: str = Field(default='', max_length=300)
    period: str = Field(default='', max_length=150)
    problem: str = Field(default='', max_length=3000)
    contribution: str = Field(default='', max_length=6000)
    technologies: list[str] = Field(default_factory=list, max_length=50)
    outcomes: list[str] = Field(default_factory=list, max_length=30)
    url: str = Field(default='', max_length=500)


class CandidateData(BaseModel):
    name: str = Field(default='', max_length=300)
    headline: str = Field(default='', max_length=300)
    location: str = Field(default='', max_length=1500)
    summary: str = Field(default='', max_length=6000)
    preferences: str = Field(default='', max_length=3000)
    contact: Contact = Field(default_factory=Contact)
    skills: list[str] = Field(default_factory=list, max_length=100)
    experience: list[Experience] = Field(default_factory=list, max_length=50)
    education: list[Education] = Field(default_factory=list, max_length=30)
    projects: list[Project] = Field(default_factory=list, max_length=100)


class Extraction(BaseModel):
    profile: CandidateData
    warnings: list[str] = Field(default_factory=list, max_length=30)
    questions: list[str] = Field(default_factory=list, max_length=20)


class NoteRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=20, max_length=40000)


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=20, max_length=60000)


class DraftRequest(BaseModel):
    profile: CandidateData


class ApproveRequest(BaseModel):
    expected_version_id: uuid.UUID
    source_id: Optional[uuid.UUID] = None
    profile: CandidateData
    master_resume: Optional[str] = Field(default=None, min_length=20, max_length=60000)
